"""
forge/core/provisioner.py
Physical Artifact Identity Capability Provisioner for 10 SHADOWS Forge.

Enforces:
CANDIDATE ARTIFACT == TESTED ARTIFACT == EXECUTED ARTIFACT

Mandatory Lifecycle:
CANDIDATE -> STAGED FILE -> SHA-256 HASH -> AST SECURITY -> DYNAMIC MODULE LOAD ->
INDEPENDENT BEHAVIORAL TESTING -> CRYPTOGRAPHIC VERIFIER RECEIPT -> VERIFIED_FOR_TASK

No authority transfer to decoupled callables or unverified lambda: True fixtures is permitted.
"""

import ast
import hashlib
import importlib.util
import inspect
import time
import types
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from forge.core.registry import CapabilityRegistry
from forge.core.substrate import (
    CapabilityDeficit,
    CapabilityKind,
    CapabilityLifecycleState,
    CapabilityManifest,
    OperatorType,
)
from loop_engine.verifiers.ast_gate import validate_ast_security


class CapabilityProvisioner:
    """
    Synthesizes, stages, AST-verifies, dynamically loads, and independently tests
    candidate capabilities, sealing execution authority to the exact verified artifact.
    """

    def __init__(self, registry: CapabilityRegistry, staging_dir: Optional[Path] = None):
        self.registry = registry
        self.staging_dir = staging_dir or Path("scratch/staging")
        self.staging_dir.mkdir(parents=True, exist_ok=True)

    def provision_capability(
        self,
        deficit: CapabilityDeficit,
        operator: OperatorType,
        candidate_code: str,
        execution_callable: Optional[Callable[..., Any]] = None,
        test_fixture: Optional[Callable[..., bool]] = None,
        input_contracts: Optional[Dict[str, Any]] = None,
        output_contracts: Optional[Dict[str, Any]] = None,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[CapabilityManifest], Optional[str]]:
        """
        Executes the physical artifact lifecycle.
        Enforces candidate == tested == executed artifact.
        """
        cap_id = f"cap_prov_{deficit.missing_capability}_{uuid.uuid4().hex[:6]}"

        # Decoupled callable check: if caller supplied a separate execution_callable that differs from candidate_code, reject
        if execution_callable is not None:
            # If execution_callable is not extracted from candidate_code, verify it doesn't violate identity
            code_str = inspect.getsource(execution_callable) if hasattr(execution_callable, "__code__") else ""
            if code_str and code_str.strip() != candidate_code.strip():
                raise ValueError(
                    "Artifact Identity Violation: Supplied execution_callable differs from candidate_code."
                )

        # Stage 1: Write candidate source code to isolated staging file
        staged_file = self.staging_dir / f"{cap_id}.py"
        staged_file.write_text(candidate_code, encoding="utf-8")

        # Stage 2: Compute SHA-256 Digest of the physical file
        raw_bytes = staged_file.read_bytes()
        artifact_hash = hashlib.sha256(raw_bytes).hexdigest()

        # Stage 3: AST Security Validation
        ast_ok, violations = validate_ast_security(candidate_code)
        if not ast_ok:
            return False, None, f"AST Security Gate Failed: {violations}"

        # Stage 4: Dynamic Module Loading from exact staged file
        try:
            spec = importlib.util.spec_from_file_location(cap_id, str(staged_file))
            if not spec or not spec.loader:
                return False, None, "Failed to create module spec from staged artifact."
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        except Exception as load_err:
            return False, None, f"Module load error in staged candidate: {str(load_err)}"

        # Stage 5: Mandatory Independent Behavioral Testing
        if not test_fixture:
            return (
                False,
                None,
                "PROVISIONING_FAILED: No independent test fixture provided; cannot advance to ISOLATED_TESTED.",
            )

        # Detect fake dummy test fixtures (e.g. lambda: True without exercising the loaded module)
        try:
            sig = inspect.signature(test_fixture)
            # If test_fixture accepts the module, pass it; otherwise invoke it
            if len(sig.parameters) >= 1:
                test_passed = test_fixture(mod)
            else:
                # If fixture takes 0 args, check if it invokes functions or is just a literal `lambda: True`
                # Inspect bytecode to detect trivial constant return True
                code_obj = getattr(test_fixture, "__code__", None)
                if code_obj and len(code_obj.co_names) == 0 and code_obj.co_consts == (None, True):
                    return (
                        False,
                        None,
                        "PROVISIONING_FAILED: Dummy 'lambda: True' fixture rejected. Test must exercise artifact behavior.",
                    )

                test_passed = test_fixture()

            if not test_passed:
                return False, None, "Isolated behavioral test failed assertion."
        except Exception as te:
            return False, None, f"Isolated test raised exception: {str(te)}"

        # Stage 6: Generate Verifier Receipt
        verifier_receipt = {
            "receipt_id": f"rcpt_{uuid.uuid4().hex[:8]}",
            "artifact_hash": artifact_hash,
            "staged_path": str(staged_file),
            "timestamp": time.time(),
            "status": "PASS",
        }

        # Stage 7: Extract primary execution callable from the verified module
        # Find the primary callable function in the module
        module_callables = [
            getattr(mod, name)
            for name in dir(mod)
            if isinstance(getattr(mod, name), types.FunctionType) and not name.startswith("_")
        ]
        if not module_callables:
            return False, None, "No executable function found in verified candidate module."

        primary_callable = module_callables[0]

        # Stage 8: Create and Register Sealed Manifest
        prov_data = provenance or {}
        prov_data.update(
            {
                "artifact_hash": artifact_hash,
                "staged_path": str(staged_file),
                "verifier_receipt": verifier_receipt,
                "deficit": deficit.missing_capability,
            }
        )

        manifest = CapabilityManifest(
            capability_id=cap_id,
            operations_supported=[operator],
            input_contracts=input_contracts or {"data": "Any"},
            output_contracts=output_contracts or {"result": "Any"},
            authority_requirements=[],
            evidence_requirements=[],
            execution_adapter=primary_callable,
            verifier=lambda res: res is not None,
            kind=CapabilityKind.REAL_PHYSICAL_ADAPTER,
            lifecycle_state=CapabilityLifecycleState.VERIFIED_FOR_TASK,
            limitations=[f"Provisioned to resolve deficit: {deficit.missing_capability}"],
            provenance=prov_data,
            version="1.0.0",
        )

        self.registry.register_capability(manifest)
        return True, manifest, None
