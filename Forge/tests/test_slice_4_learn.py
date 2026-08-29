from forge.core.evaluate import evaluate
from forge.core.learn import learn_if_earned
from forge.core.schema import validate_contract


def test_learn_clean_run_no_noise(test_store):
    task_spec = {
        "task_id": "task-401",
        "objective": "Simple clean task",
        "deliverable": {"kind": "ANSWER", "description": "Answer text"},
        "constraints": [],
        "knowns": [],
        "unknowns": [],
        "assumptions": [],
        "success_conditions": ["Produces valid text"],
        "requires_external_action": False,
        "reversibility": "REVERSIBLE",
        "risk": "LOW",
    }

    result = {"status": "COMPLETE", "result": "Clean output"}
    ev = evaluate(task_spec, result)
    assert ev["success"] is True

    record = learn_if_earned(task_spec, result, ev, test_store)
    assert validate_contract("LearningRecord", record) is True
    assert record["outcome"] == "SUCCESS"
    assert record["promotion"] == "NONE"

    # Zero noise preserved in database on clean success
    learnings = test_store.get_learnings_for_task("task-401")
    assert len(learnings) == 0


def test_learn_permission_error_promotes_regression_test(test_store):
    task_spec = {
        "task_id": "task-402",
        "objective": "Mutate file target",
        "deliverable": {"kind": "ACTION", "description": "Write target file"},
        "constraints": [],
        "knowns": [],
        "unknowns": [],
        "assumptions": [],
        "success_conditions": ["File exists with expected bytes"],
        "requires_external_action": True,
        "reversibility": "REVERSIBLE",
        "risk": "MEDIUM",
    }

    receipt = {
        "execution_id": "exec-402",
        "transaction_id": "tx-402",
        "attempt_id": "att-402",
        "authorization_id": "auth-402",
        "operation_hash": "hash-402",
        "outcome": "FAILED",
        "side_effect_committed": False,
        "output": {},
        "error": "PermissionError: Target path escapes sandbox root",
    }

    ev = evaluate(task_spec, receipt)
    assert ev["success"] is False

    record = learn_if_earned(task_spec, receipt, ev, test_store)
    assert validate_contract("LearningRecord", record) is True
    assert record["outcome"] == "FAILURE"
    assert record["promotion"] == "REGRESSION_TEST"
    assert record["reproducible"] is True

    # Stored in SQLite for future test regression suite
    learnings = test_store.get_learnings_for_task("task-402")
    assert len(learnings) == 1
    assert learnings[0]["promotion"] == "REGRESSION_TEST"


def test_store_cas_optimistic_locking(test_store):
    test_store.record_transaction("tx-cas-1", "task-cas-1", state="OPEN")
    tx = test_store.get_transaction("tx-cas-1")
    assert tx["revision"] == 1
    assert tx["state"] == "OPEN"

    # Successful CAS update with revision 1 -> 2
    success = test_store.update_transaction_cas("tx-cas-1", expected_revision=1, new_state="COMMITTED")
    assert success is True

    tx_updated = test_store.get_transaction("tx-cas-1")
    assert tx_updated["revision"] == 2
    assert tx_updated["state"] == "COMMITTED"
    assert tx_updated["parent_hash"] is not None

    # Stale CAS update with outdated revision 1 must be REJECTED
    stale_attempt = test_store.update_transaction_cas("tx-cas-1", expected_revision=1, new_state="ROLLEDBACK")
    assert stale_attempt is False

    # State remains COMMITTED and revision remains 2
    assert test_store.get_transaction("tx-cas-1")["state"] == "COMMITTED"
