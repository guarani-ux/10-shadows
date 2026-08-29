//! main.rs — CLI entrypoint `ts` for 10 SHADOWS Trusted Kernel.

use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use ten_shadows_kernel::db::KernelDb;
use ten_shadows_kernel::evidence::VerificationType;
use ten_shadows_kernel::predicate::evaluate_receipt;
use ten_shadows_kernel::receipt::TenShadowsReceipt;
use ten_shadows_kernel::state_machine::KernelRun;
use ten_shadows_kernel::verifier::SubprocessVerifier;

fn resolve_git_head(target: &Path) -> Option<String> {
    let output = Command::new("git")
        .args(["rev-parse", "HEAD"])
        .current_dir(target)
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

fn print_usage() {
    println!("Usage:");
    println!("  ts run --target <path> --objective <objective> [--task-id <id>] [--mutate] [--provider <gemini|deterministic>] [--model <model>]");
    println!("  ts verify-receipt <receipt_json>");
    println!("  ts verify-production <receipt_json>");
    println!("  ts status");
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        print_usage();
        return Ok(());
    }

    let db_dir = PathBuf::from(".kernel_db");
    let receipts_dir = PathBuf::from(".receipts");
    fs::create_dir_all(&receipts_dir)?;

    let db = KernelDb::open(&db_dir)?;

    match args[1].as_str() {
        "run" => {
            let mut objective = String::new();
            let mut target = PathBuf::from(".");
            let mut task_id = None;
            let mut is_mutation_run = false;
            let mut requested_provider = "gemini".to_string();
            let mut requested_model = "gemini-3.7-flash".to_string();

            let mut i = 2;
            while i < args.len() {
                match args[i].as_str() {
                    "--objective" | "-o" if i + 1 < args.len() => {
                        objective = args[i + 1].clone();
                        i += 2;
                    }
                    "--target" | "-t" if i + 1 < args.len() => {
                        target = PathBuf::from(&args[i + 1]);
                        i += 2;
                    }
                    "--task-id" if i + 1 < args.len() => {
                        task_id = Some(args[i + 1].clone());
                        i += 2;
                    }
                    "--provider" | "-p" if i + 1 < args.len() => {
                        requested_provider = args[i + 1].clone();
                        i += 2;
                    }
                    "--model" | "-m" if i + 1 < args.len() => {
                        requested_model = args[i + 1].clone();
                        i += 2;
                    }
                    "--mutate" => {
                        is_mutation_run = true;
                        i += 1;
                    }
                    _ => {
                        i += 1;
                    }
                }
            }

            if objective.is_empty() {
                eprintln!("Error: --objective is required.");
                std::process::exit(1);
            }

            println!("========================================================");
            println!("       TEN SHADOWS TRUSTED KERNEL (RUST CORE v3.0)      ");
            println!("========================================================");

            let target_canonical = target.canonicalize().unwrap_or(target.clone());
            let starting_head = resolve_git_head(&target_canonical);

            // Step 1: Run Ingress & State Machine Initialization (Typestate: Created)
            let run_created = KernelRun::new(&objective, &target_canonical, task_id);
            let run_id = run_created.run_id.clone();
            let task_id_str = run_created.task_id.clone();
            let obj_hash = run_created.objective_hash.clone();

            println!("\n[KERNEL] Run Ingress Accepted:");
            println!("  Run ID:             {}", run_id);
            println!("  Task ID:            {}", task_id_str);
            println!("  Objective Hash:     {}", obj_hash);
            println!("  Strategy:           {:?}", run_created.strategy);
            println!("  Capabilities:       {:?}", run_created.capabilities);
            println!("  Requested Provider: {}", requested_provider);
            println!("  Requested Model:    {}", requested_model);

            // Step 2: Record Run Creation in Journal DB
            let start_commit_str = starting_head
                .clone()
                .unwrap_or_else(|| "UNKNOWN_NON_GIT".into());
            db.record_run_created(&run_id, &task_id_str, &obj_hash, &start_commit_str)?;

            // Step 3: Capture Baseline (Typestate: BaselineCaptured)
            let run_baseline = run_created.capture_baseline(starting_head.clone());

            // Step 4: Workspace Preparation (Typestate: WorkspaceReady)
            let (run_ws, eval_path) = if is_mutation_run && starting_head.is_some() {
                let head = starting_head.as_deref().unwrap_or("UNKNOWN");
                println!(
                    "[KERNEL] Spawning isolated GovernedWorkspace from baseline {}...",
                    head
                );
                let ws_run = run_baseline.prepare_governed_workspace(None)?;
                let p = ws_run
                    .workspace_path
                    .clone()
                    .unwrap_or_else(|| target_canonical.clone());
                (ws_run, p)
            } else {
                println!(
                    "[KERNEL] Mounting read-only audit workspace for target {}...",
                    target_canonical.display()
                );
                let ws_run = run_baseline.prepare_audit_workspace(&target_canonical);
                (ws_run, target_canonical.clone())
            };

            // Step 5: Authorize Worker (Typestate: WorkerAuthorized)
            let worker_id = if is_mutation_run {
                format!("forge_builder_{}", task_id_str)
            } else {
                format!("svris_auditor_{}", task_id_str)
            };
            let run_auth = run_ws.authorize_worker(&worker_id);

            // Step 6: Dispatch Worker & Record Candidate (Typestate: CandidateProduced)
            let run_cand = if is_mutation_run {
                println!(
                    "[KERNEL] Dispatching Worker '{}' via Language-Neutral Dispatcher...",
                    worker_id
                );
                println!("  Target Provider: {}", requested_provider);
                println!("  Target Model:    {}", requested_model);
                run_auth.dispatch_and_produce_candidate(
                    &requested_provider,
                    &requested_model,
                    None,
                )?
            } else {
                let current_head = resolve_git_head(&eval_path);
                let cand_sha = current_head
                    .clone()
                    .unwrap_or_else(|| "UNTRACKED_WORKSPACE".into());
                run_auth.record_external_candidate(
                    &cand_sha,
                    "Baseline audit execution (zero mutations)",
                )
            };

            // Step 7: Independent Verification Subprocess (Typestate: Verified)
            println!(
                "\n[KERNEL] Executing Independent Verification Subprocess on {}...",
                eval_path.display()
            );
            let verification_rec = SubprocessVerifier::execute(
                &eval_path,
                &task_id_str,
                &worker_id,
                None,
                VerificationType::IndependentBehavioralOracle,
            );

            println!("  Verifier ID:        {}", verification_rec.verifier_id);
            println!(
                "  Tests Passed:       {}/{}",
                verification_rec.tests_passed, verification_rec.tests_collected
            );
            println!("  Exit Code:          {}", verification_rec.exit_code);
            println!("  Status:             {}", verification_rec.verified_status);

            let run_verified = run_cand.record_verification(verification_rec);

            // Step 8: Promotion & Receipt Sealing (Typestate: Promoted)
            let (_run_promoted, receipt) = run_verified.promote_and_seal();

            let receipt_json = serde_json::to_string_pretty(&receipt)?;
            let receipt_path = receipts_dir.join(format!("{}_receipt.json", run_id));
            fs::write(&receipt_path, &receipt_json)?;

            db.record_receipt(
                &receipt.run_id,
                &receipt.task_id,
                &start_commit_str,
                receipt.final_head.as_deref(),
                &receipt.objective_hash,
                &format!("{:?}", receipt.final_status),
                &receipt_json,
            )?;

            println!("\n========================================================");
            println!("              TEN SHADOWS RUN CONCLUDED                 ");
            println!("========================================================");
            println!("Run ID:               {}", receipt.run_id);
            println!("Final Status:         {:?}", receipt.final_status);
            println!("Candidate Lineage:    {}", receipt.candidate_classification);
            println!("Receipt Signature:    {}", &receipt.receipt_signature[..16]);
            println!("Receipt File:         {}", receipt_path.display());

            let report = evaluate_receipt(&receipt, Some(&db));
            println!("\n[PREDICATE EVALUATION]");
            println!("  Execution Valid:     {}", report.is_execution_valid);
            println!("  Production Valid:    {}", report.is_production_valid);
            println!(
                "  Objective Satisfied: {}",
                report.is_objective_accomplished
            );
        }

        "verify-receipt" if args.len() >= 3 => {
            let receipt_path = PathBuf::from(&args[2]);
            println!("========================================================");
            println!("       TEN SHADOWS EXECUTION RECEIPT VERIFICATION       ");
            println!("========================================================");
            println!("Target: {}", receipt_path.display());

            let data = fs::read_to_string(&receipt_path)?;
            let parsed: TenShadowsReceipt = serde_json::from_str(&data)?;
            let report = evaluate_receipt(&parsed, Some(&db));

            if report.is_execution_valid {
                println!("\n[VERIFICATION PASSED] Valid kernel-governed execution receipt.");
            } else {
                println!("\n[VERIFICATION FAILED] Execution receipt invalid:");
                for err in report.errors {
                    println!("  - {}", err);
                }
                std::process::exit(1);
            }
        }

        "verify-production" if args.len() >= 3 => {
            let receipt_path = PathBuf::from(&args[2]);
            println!("========================================================");
            println!("       TEN SHADOWS PRODUCTION CUSTODY VERIFICATION      ");
            println!("========================================================");
            println!("Target: {}", receipt_path.display());

            let data = fs::read_to_string(&receipt_path)?;
            let parsed: TenShadowsReceipt = serde_json::from_str(&data)?;
            let report = evaluate_receipt(&parsed, Some(&db));

            if report.is_production_valid {
                println!("\n[VERIFICATION PASSED] Candidate was ACTUALLY produced under Ten Shadows custody.");
            } else {
                println!(
                    "\n[VERIFICATION FAILED] Candidate was NOT produced under Ten Shadows custody:"
                );
                for err in report.errors {
                    println!("  - {}", err);
                }
                std::process::exit(1);
            }
        }

        "verify-objective" if args.len() >= 3 => {
            let receipt_path = PathBuf::from(&args[2]);
            println!("========================================================");
            println!("       TEN SHADOWS OBJECTIVE SUFFICIENCY VERIFICATION   ");
            println!("========================================================");
            println!("Target: {}", receipt_path.display());

            let data = fs::read_to_string(&receipt_path)?;
            let parsed: TenShadowsReceipt = serde_json::from_str(&data)?;
            let report = evaluate_receipt(&parsed, Some(&db));

            if report.is_objective_accomplished {
                println!("\n[VERIFICATION PASSED] Objective was AUTHORITATIVELY satisfied under Law 6 Sufficiency.");
            } else {
                println!("\n[VERIFICATION FAILED] Objective was NOT accomplished:");
                for err in report.errors {
                    println!("  - {}", err);
                }
                std::process::exit(1);
            }
        }

        "status" => {
            println!("Ten Shadows Kernel DB connected at {}", db_dir.display());
        }

        _ => {
            print_usage();
        }
    }

    Ok(())
}
