//! dispatcher.rs — Rust Trusted Kernel interface to the Language-Neutral Worker Dispatcher.

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::error::Error;
use std::fmt;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum DispatchError {
    DispatcherProcessFailed(String),
    MalformedAuthorization(String),
    TokenVerificationFailed(String),
    WorkspaceEscapeDetected(String),
    InvocationMismatch(String),
    Timeout(String),
}

impl fmt::Display for DispatchError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            DispatchError::DispatcherProcessFailed(s) => {
                write!(f, "DISPATCHER PROCESS FAILED: {}", s)
            }
            DispatchError::MalformedAuthorization(s) => write!(f, "MALFORMED AUTHORIZATION: {}", s),
            DispatchError::TokenVerificationFailed(s) => {
                write!(f, "TOKEN VERIFICATION FAILED: {}", s)
            }
            DispatchError::WorkspaceEscapeDetected(s) => {
                write!(f, "WORKSPACE ESCAPE DETECTED: {}", s)
            }
            DispatchError::InvocationMismatch(s) => write!(f, "INVOCATION MISMATCH: {}", s),
            DispatchError::Timeout(s) => write!(f, "WORKER TIMEOUT: {}", s),
        }
    }
}

impl Error for DispatchError {}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkerAuthorization {
    pub protocol_version: String,
    pub run_id: String,
    pub task_id: String,
    pub invocation_id: String,
    pub worker_id: String,
    pub worker_role: String,
    pub objective: String,
    pub objective_hash: String,
    pub baseline_sha: String,
    pub governed_workspace_path: String,
    pub governed_workspace_identity: String,
    pub requested_provider: String,
    pub requested_model: String,
    pub allowed_capabilities: Vec<String>,
    pub filesystem_boundary: String,
    pub timeout_seconds: f64,
    pub attempt_number: usize,
    pub failure_evidence: Option<String>,
    pub authorized_at: String,
    pub authorization_token: String,
}

impl WorkerAuthorization {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        run_id: &str,
        task_id: &str,
        invocation_id: &str,
        worker_id: &str,
        worker_role: &str,
        objective: &str,
        objective_hash: &str,
        baseline_sha: &str,
        governed_workspace_path: &Path,
        requested_provider: &str,
        requested_model: &str,
        attempt_number: usize,
        failure_evidence: Option<String>,
        authorized_at: &str,
    ) -> Self {
        let ws_str = governed_workspace_path.display().to_string();
        let token = Self::compute_token(
            run_id,
            task_id,
            invocation_id,
            objective_hash,
            baseline_sha,
            &ws_str,
            attempt_number,
        );

        Self {
            protocol_version: "1.0.0".into(),
            run_id: run_id.to_string(),
            task_id: task_id.to_string(),
            invocation_id: invocation_id.to_string(),
            worker_id: worker_id.to_string(),
            worker_role: worker_role.to_string(),
            objective: objective.to_string(),
            objective_hash: objective_hash.to_string(),
            baseline_sha: baseline_sha.to_string(),
            governed_workspace_path: ws_str.clone(),
            governed_workspace_identity: format!("governed_ws_{}_{}", task_id, attempt_number),
            requested_provider: requested_provider.to_string(),
            requested_model: requested_model.to_string(),
            allowed_capabilities: vec!["CODE_SYNTHESIS".into(), "ISOLATED_FS_MUTATION".into()],
            filesystem_boundary: ws_str,
            timeout_seconds: 120.0,
            attempt_number,
            failure_evidence,
            authorized_at: authorized_at.to_string(),
            authorization_token: token,
        }
    }

    pub fn compute_token(
        run_id: &str,
        task_id: &str,
        invocation_id: &str,
        objective_hash: &str,
        baseline_sha: &str,
        governed_workspace_path: &str,
        attempt_number: usize,
    ) -> String {
        let raw = format!(
            "{}:{}:{}:{}:{}:{}:{}",
            run_id,
            task_id,
            invocation_id,
            objective_hash,
            baseline_sha,
            governed_workspace_path,
            attempt_number
        );
        let mut hasher = Sha256::new();
        hasher.update(raw.as_bytes());
        format!("{:x}", hasher.finalize())
    }

    pub fn verify_token(&self) -> bool {
        let expected = Self::compute_token(
            &self.run_id,
            &self.task_id,
            &self.invocation_id,
            &self.objective_hash,
            &self.baseline_sha,
            &self.governed_workspace_path,
            self.attempt_number,
        );
        self.authorization_token == expected
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProviderUsage {
    pub prompt_tokens: Option<u64>,
    pub candidate_tokens: Option<u64>,
    pub total_tokens: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkerExecutionResult {
    pub protocol_version: String,
    pub run_id: String,
    pub invocation_id: String,
    pub worker_id: String,
    pub requested_provider: String,
    pub requested_model: String,
    pub resolved_provider: String,
    pub resolved_model: String,
    pub provider_invocation_id: Option<String>,
    pub modality: String,
    pub started_at: String,
    pub ended_at: String,
    pub duration_seconds: f64,
    pub exit_status: String,
    pub usage: Option<ProviderUsage>,
    pub output_digest: String,
    pub workspace_before_sha: String,
    pub workspace_after_sha: String,
    pub files_changed: Vec<String>,
    pub provider_receipt: Option<serde_json::Value>,
    pub errors: Vec<String>,
    pub completion_status: String,
}

pub struct WorkerDispatcher;

impl WorkerDispatcher {
    fn resolve_repo_root() -> PathBuf {
        let mut curr = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
        for _ in 0..5 {
            if curr.join("loop_engine").exists() {
                return curr;
            }
            if let Some(parent) = curr.parent() {
                curr = parent.to_path_buf();
            } else {
                break;
            }
        }
        PathBuf::from(".")
    }

    /// Dispatches the authorized worker by invoking the worker dispatcher process.
    pub fn dispatch(
        auth: &WorkerAuthorization,
        python_executable: Option<&str>,
    ) -> Result<WorkerExecutionResult, DispatchError> {
        if !auth.verify_token() {
            return Err(DispatchError::TokenVerificationFailed(
                "WorkerAuthorization token validation failed".into(),
            ));
        }

        let millis = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis();
        let tmp_dir = std::env::temp_dir().join("10_shadows_ipc");
        fs::create_dir_all(&tmp_dir)
            .map_err(|e| DispatchError::DispatcherProcessFailed(e.to_string()))?;

        let auth_path = tmp_dir.join(format!("auth_{}_{}.json", auth.invocation_id, millis));
        let out_path = tmp_dir.join(format!("result_{}_{}.json", auth.invocation_id, millis));

        let auth_json = serde_json::to_string_pretty(auth)
            .map_err(|e| DispatchError::MalformedAuthorization(e.to_string()))?;
        fs::write(&auth_path, auth_json)
            .map_err(|e| DispatchError::DispatcherProcessFailed(e.to_string()))?;

        let repo_root = Self::resolve_repo_root();
        let py = python_executable.unwrap_or("python");
        let output = Command::new(py)
            .args([
                "-m",
                "loop_engine.dispatcher.worker_dispatcher",
                "--auth",
                auth_path.to_str().unwrap(),
                "--output",
                out_path.to_str().unwrap(),
            ])
            .current_dir(&repo_root)
            .env("PYTHONPATH", &repo_root)
            .output()
            .map_err(|e| {
                DispatchError::DispatcherProcessFailed(format!("Failed to spawn dispatcher: {}", e))
            })?;

        // Cleanup auth request file
        let _ = fs::remove_file(&auth_path);

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(DispatchError::DispatcherProcessFailed(format!(
                "Dispatcher process exited with code {}: {}",
                output.status.code().unwrap_or(-1),
                stderr
            )));
        }

        if !out_path.exists() {
            return Err(DispatchError::DispatcherProcessFailed(
                "Dispatcher produced no result JSON file".into(),
            ));
        }

        let result_json = fs::read_to_string(&out_path).map_err(|e| {
            DispatchError::DispatcherProcessFailed(format!("Cannot read result JSON: {}", e))
        })?;
        let _ = fs::remove_file(&out_path);

        let result: WorkerExecutionResult = serde_json::from_str(&result_json).map_err(|e| {
            DispatchError::DispatcherProcessFailed(format!("Failed to parse result JSON: {}", e))
        })?;

        // Invariant checks on returned result
        if result.run_id != auth.run_id || result.invocation_id != auth.invocation_id {
            return Err(DispatchError::InvocationMismatch(format!(
                "Result invocation '{}' does not match authorization '{}'",
                result.invocation_id, auth.invocation_id
            )));
        }

        Ok(result)
    }
}
