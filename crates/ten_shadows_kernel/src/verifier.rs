//! verifier.rs — Subprocess Verification Harness & Test Oracle.

use crate::evidence::{EvidenceModality, EvidencePurpose, VerificationType};
use crate::receipt::IndependentVerificationRecord;
use crate::time_utils::current_timestamp_rfc3339;
use sha2::{Digest, Sha256};
use std::path::Path;
use std::process::Command;
use std::time::Instant;

pub struct SubprocessVerifier;

impl SubprocessVerifier {
    pub fn execute(
        target_path: &Path,
        task_id: &str,
        builder_id: &str,
        custom_cmd: Option<Vec<String>>,
        verifier_type: VerificationType,
    ) -> IndependentVerificationRecord {
        let verifier_id = format!("svris_independent_verifier_{}", task_id);
        let start = Instant::now();

        let (cmd_bin, args) = if let Some(cmd_parts) = custom_cmd {
            (cmd_parts[0].clone(), cmd_parts[1..].to_vec())
        } else {
            let mut args = vec!["-v".to_string(), "--tb=short".to_string()];
            if target_path.join("tests").exists() {
                args.insert(0, "tests/".to_string());
            }
            ("pytest".to_string(), args)
        };

        let output_res = Command::new(&cmd_bin)
            .args(&args)
            .current_dir(target_path)
            .output();

        let duration = start.elapsed().as_secs_f64().max(0.001);

        match output_res {
            Ok(output) => {
                let stdout = String::from_utf8_lossy(&output.stdout).to_string();
                let stderr = String::from_utf8_lossy(&output.stderr).to_string();
                let full_trace = format!("{}\n{}", stdout, stderr);
                let exit_code = output.status.code().unwrap_or(1);

                let passed_cnt = Self::extract_count(&full_trace, " passed").unwrap_or(if exit_code == 0 { 1 } else { 0 });
                let failed_cnt = Self::extract_count(&full_trace, " failed").unwrap_or(if exit_code != 0 { 1 } else { 0 });

                let mut hasher = Sha256::new();
                hasher.update(format!("{}:{}", cmd_bin, full_trace).as_bytes());
                let test_digest = format!("{:x}", hasher.finalize());

                let status = if exit_code == 0 { "PASS" } else { "FAIL" };

                IndependentVerificationRecord {
                    verifier_id,
                    verifier_type,
                    builder_id: builder_id.to_string(),
                    modality: EvidenceModality::DeterministicTest,
                    purpose: EvidencePurpose::BehavioralVerification,
                    test_digest,
                    tests_collected: passed_cnt + failed_cnt,
                    tests_passed: passed_cnt,
                    tests_failed: failed_cnt,
                    exit_code,
                    duration_seconds: (duration * 1000.0).round() / 1000.0,
                    falsification_attempted: true,
                    verified_status: status.into(),
                    execution_trace: Some(full_trace.chars().take(2000).collect()),
                    tested_effect: None,
                    verifier_spec_digest: None,
                    timestamp: current_timestamp_rfc3339(),
                }
            }
            Err(e) => {
                IndependentVerificationRecord {
                    verifier_id,
                    verifier_type,
                    builder_id: builder_id.to_string(),
                    modality: EvidenceModality::DeterministicTest,
                    purpose: EvidencePurpose::BehavioralVerification,
                    test_digest: format!("{:x}", Sha256::digest(format!("{}", e).as_bytes())),
                    tests_collected: 0,
                    tests_passed: 0,
                    tests_failed: 1,
                    exit_code: 1,
                    duration_seconds: (duration * 1000.0).round() / 1000.0,
                    falsification_attempted: true,
                    verified_status: "FAIL".into(),
                    execution_trace: Some(format!("Subprocess execution failed: {}", e)),
                    tested_effect: None,
                    verifier_spec_digest: None,
                    timestamp: current_timestamp_rfc3339(),
                }
            }
        }
    }

    fn extract_count(trace: &str, keyword: &str) -> Option<usize> {
        if let Some(pos) = trace.find(keyword) {
            let slice = &trace[..pos];
            let words: Vec<&str> = slice.split_whitespace().collect();
            if let Some(last) = words.last() {
                if let Ok(num) = last.parse::<usize>() {
                    return Some(num);
                }
            }
        }
        None
    }
}
