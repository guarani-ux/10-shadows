//! db.rs — Pure-Rust Immutable Append-Only WAL Journal for Ten Shadows Kernel.

use crate::time_utils::current_timestamp_rfc3339;
use serde::{Deserialize, Serialize};
use std::fs::{self, File, OpenOptions};
use std::io::{self, BufRead, BufReader, Write};
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RunRecord {
    pub run_id: String,
    pub task_id: String,
    pub shadow_id: u32,
    pub domain_code: String,
    pub source_commit: String,
    pub objective_hash: String,
    pub status: String,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReceiptDbRecord {
    pub run_id: String,
    pub task_id: String,
    pub stage: String,
    pub attempt: usize,
    pub candidate_hash: Option<String>,
    pub source_commit: String,
    pub spec_hash: String,
    pub status: String,
    pub promotion_decision: String,
    pub receipt_json: String,
    pub created_at: String,
}

pub struct KernelDb {
    runs_file: PathBuf,
    receipts_file: PathBuf,
}

impl KernelDb {
    pub fn open(base_dir: &Path) -> io::Result<Self> {
        fs::create_dir_all(base_dir)?;
        let runs_file = base_dir.join("runs_journal.jsonl");
        let receipts_file = base_dir.join("receipts_journal.jsonl");

        if !runs_file.exists() {
            File::create(&runs_file)?;
        }
        if !receipts_file.exists() {
            File::create(&receipts_file)?;
        }

        Ok(Self {
            runs_file,
            receipts_file,
        })
    }

    pub fn record_run_created(
        &self,
        run_id: &str,
        task_id: &str,
        objective_hash: &str,
        source_commit: &str,
    ) -> io::Result<()> {
        let now = current_timestamp_rfc3339();
        let record = RunRecord {
            run_id: run_id.to_string(),
            task_id: task_id.to_string(),
            shadow_id: 1,
            domain_code: "general_engineering".into(),
            source_commit: source_commit.to_string(),
            objective_hash: objective_hash.to_string(),
            status: "CREATED".into(),
            created_at: now.clone(),
            updated_at: now,
        };

        let mut file = OpenOptions::new().create(true).append(true).open(&self.runs_file)?;
        let line = serde_json::to_string(&record).map_err(|e| io::Error::new(io::ErrorKind::Other, e))?;
        writeln!(file, "{}", line)?;
        file.sync_all()?;
        Ok(())
    }

    pub fn record_receipt(
        &self,
        run_id: &str,
        task_id: &str,
        starting_head: &str,
        final_head: Option<&str>,
        objective_hash: &str,
        status: &str,
        receipt_json: &str,
    ) -> io::Result<()> {
        let now = current_timestamp_rfc3339();
        let record = ReceiptDbRecord {
            run_id: run_id.to_string(),
            task_id: task_id.to_string(),
            stage: "SEALED".into(),
            attempt: 1,
            candidate_hash: final_head.map(|s| s.to_string()),
            source_commit: starting_head.to_string(),
            spec_hash: objective_hash.to_string(),
            status: status.to_string(),
            promotion_decision: "PROMOTED".into(),
            receipt_json: receipt_json.to_string(),
            created_at: now,
        };

        let mut file = OpenOptions::new().create(true).append(true).open(&self.receipts_file)?;
        let line = serde_json::to_string(&record).map_err(|e| io::Error::new(io::ErrorKind::Other, e))?;
        writeln!(file, "{}", line)?;
        file.sync_all()?;
        Ok(())
    }

    pub fn has_run(&self, run_id: &str) -> bool {
        if let Ok(file) = File::open(&self.runs_file) {
            let reader = BufReader::new(file);
            for line in reader.lines().flatten() {
                if let Ok(record) = serde_json::from_str::<RunRecord>(&line) {
                    if record.run_id == run_id {
                        return true;
                    }
                }
            }
        }
        false
    }

    pub fn get_run_objective_hash(&self, run_id: &str) -> Option<String> {
        if let Ok(file) = File::open(&self.runs_file) {
            let reader = BufReader::new(file);
            for line in reader.lines().flatten() {
                if let Ok(record) = serde_json::from_str::<RunRecord>(&line) {
                    if record.run_id == run_id {
                        return Some(record.objective_hash);
                    }
                }
            }
        }
        None
    }
}
