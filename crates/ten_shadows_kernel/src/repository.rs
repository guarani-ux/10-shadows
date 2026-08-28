//! repository.rs — Typed Repository Roles and Hard Path Safety Guards for 10 SHADOWS.
//!
//! Mechanically separates:
//! - AuthoritativeSource (Source of truth, strictly read-only for inspection)
//! - GovernedWorkspace (Run-owned ephemeral isolated worktree for candidate production)
//! - DisposableTestRepository (Temporary repository for test integration)
//! - ExternalTarget (External code target for read-only audit)

use std::error::Error;
use std::fmt;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RepositoryRoleError {
    AuthoritativeSourceMutationForbidden(String),
    WorkspaceEscapingBoundary(String),
    InvalidGitRepository(String),
    BaselineDiverged(String),
}

impl fmt::Display for RepositoryRoleError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            RepositoryRoleError::AuthoritativeSourceMutationForbidden(s) => {
                write!(f, "AUTHORITATIVE SOURCE MUTATION FORBIDDEN: {}", s)
            }
            RepositoryRoleError::WorkspaceEscapingBoundary(s) => {
                write!(f, "WORKSPACE BOUNDARY ESCAPE: {}", s)
            }
            RepositoryRoleError::InvalidGitRepository(s) => {
                write!(f, "INVALID GIT REPOSITORY: {}", s)
            }
            RepositoryRoleError::BaselineDiverged(s) => {
                write!(f, "BASELINE DIVERGED BEFORE PROMOTION: {}", s)
            }
        }
    }
}

impl Error for RepositoryRoleError {}

/// Authoritative Source Repository wrapper.
#[derive(Debug, Clone)]
pub struct AuthoritativeSource {
    pub root: PathBuf,
}

impl AuthoritativeSource {
    pub fn new(path: &Path) -> Result<Self, RepositoryRoleError> {
        let canonical = path.canonicalize().map_err(|e| {
            RepositoryRoleError::InvalidGitRepository(format!("Cannot canonicalize path '{}': {}", path.display(), e))
        })?;
        Ok(Self { root: canonical })
    }

    pub fn capture_head(&self) -> Option<String> {
        let output = Command::new("git")
            .args(["rev-parse", "HEAD"])
            .current_dir(&self.root)
            .output()
            .ok()?;

        if output.status.success() {
            let head = String::from_utf8_lossy(&output.stdout).trim().to_string();
            if head.len() == 40 {
                return Some(head);
            }
        }
        None
    }
}

/// Governed Workspace: An isolated, run-owned worktree or directory for worker execution.
#[derive(Debug, Clone)]
pub struct GovernedWorkspace {
    pub run_id: String,
    pub source_root: PathBuf,
    pub workspace_root: PathBuf,
    pub branch_name: String,
    pub baseline_sha: String,
}

impl GovernedWorkspace {
    /// Creates an isolated ephemeral Git worktree rooted at exact baseline_sha.
    pub fn create_ephemeral(
        run_id: &str,
        source: &AuthoritativeSource,
        baseline_sha: &str,
        base_worktrees_dir: Option<&Path>,
    ) -> Result<Self, RepositoryRoleError> {
        let wt_base = base_worktrees_dir
            .map(|p| p.to_path_buf())
            .unwrap_or_else(|| std::env::temp_dir().join("10_shadows_worktrees"));
        
        fs::create_dir_all(&wt_base).map_err(|e| {
            RepositoryRoleError::InvalidGitRepository(format!("Failed to create worktrees dir: {}", e))
        })?;

        let safe_run_id = run_id.replace(['/', '\\', ':', ' '], "_");
        let branch_name = format!("sandbox/governed_{}", safe_run_id);
        let workspace_path = wt_base.join(format!("wt_{}", safe_run_id));

        // Invariant: Path safety guard — workspace must NOT be identical to source root!
        if workspace_path == source.root {
            return Err(RepositoryRoleError::AuthoritativeSourceMutationForbidden(format!(
                "Workspace path '{}' cannot be the AuthoritativeSource root!",
                workspace_path.display()
            )));
        }

        // Clean up any stale worktree at this path
        if workspace_path.exists() {
            let _ = fs::remove_dir_all(&workspace_path);
        }

        let output = Command::new("git")
            .args(["worktree", "add", "-b", &branch_name, workspace_path.to_str().unwrap(), baseline_sha])
            .current_dir(&source.root)
            .output()
            .map_err(|e| RepositoryRoleError::InvalidGitRepository(format!("Failed to spawn git worktree command: {}", e)))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(RepositoryRoleError::InvalidGitRepository(format!(
                "git worktree add failed: {}",
                stderr
            )));
        }

        let ws_canonical = workspace_path.canonicalize().unwrap_or(workspace_path);

        Ok(Self {
            run_id: run_id.to_string(),
            source_root: source.root.clone(),
            workspace_root: ws_canonical,
            branch_name,
            baseline_sha: baseline_sha.to_string(),
        })
    }

    /// Captures the candidate commit SHA from within the governed workspace.
    pub fn capture_candidate_head(&self) -> Option<String> {
        let output = Command::new("git")
            .args(["rev-parse", "HEAD"])
            .current_dir(&self.workspace_root)
            .output()
            .ok()?;

        if output.status.success() {
            let head = String::from_utf8_lossy(&output.stdout).trim().to_string();
            if head.len() == 40 {
                return Some(head);
            }
        }
        None
    }

    /// Safely destroys the worktree and deletes the sandbox branch from the source repo.
    pub fn destroy(self) {
        let _ = Command::new("git")
            .args(["worktree", "remove", "--force", self.workspace_root.to_str().unwrap_or_default()])
            .current_dir(&self.source_root)
            .output();

        let _ = Command::new("git")
            .args(["worktree", "prune"])
            .current_dir(&self.source_root)
            .output();

        let _ = Command::new("git")
            .args(["branch", "-D", &self.branch_name])
            .current_dir(&self.source_root)
            .output();

        if self.workspace_root.exists() {
            let _ = fs::remove_dir_all(&self.workspace_root);
        }
    }
}
