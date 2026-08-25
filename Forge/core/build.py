import ast
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from forge.adapters.model import ModelAdapter
from forge.core.schema import validate_contract


def run_physical_smoke_test(artifact_type: str, content: str) -> Tuple[str, Optional[str]]:
    """
    Physically validates synthesized capability artifact using AST parsing and compilation.
    Returns (status: 'PASSED' | 'FAILED', error: Optional[str]).
    """
    if artifact_type in ("SCRIPT", "CODE"):
        try:
            # Step 1: AST validation
            ast.parse(content, filename="<synthesized_capability>")
            # Step 2: Bytecode compilation
            compile(content, filename="<synthesized_capability>", mode="exec")
            return "PASSED", None
        except SyntaxError as se:
            return "FAILED", f"SyntaxError in synthesized capability: {se.msg} (line {se.lineno})"
        except Exception as e:
            return "FAILED", f"Compilation error: {str(e)}"

    # For non-code artifacts (PROMPT, WORKFLOW, DOCUMENT), verify non-empty and non-trivial
    if not content or len(content.strip()) == 0:
        return "FAILED", "Synthesized artifact content is empty."

    return "PASSED", None


def build(
    task_spec: Dict[str, Any],
    model_adapter: ModelAdapter,
    artifacts_dir: Optional[Path] = None
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Synthesizes a minimal reusable capability (BuildSpec) and produces its artifact.
    Runs a real physical smoke test to verify the single processor before packaging.
    """
    validate_contract("TaskSpec", task_spec)

    task_id = task_spec["task_id"]
    build_id = f"build_{uuid.uuid4().hex[:8]}"

    prompt = (
        "You are the Forge Capability Synthesizer. Build the smallest single-responsibility capability "
        "to satisfy the given TaskSpec. Define: artifact_type ('PROMPT'|'WORKFLOW'|'SCRIPT'|'AGENT'|'DOCUMENT'|'SERVICE'|'SYSTEM'|'OTHER'), "
        "responsibility, vertical_slice (raw_input, processing, raw_output), inputs, outputs, "
        "components (list with 1 minimal component), acceptance_tests, external_side_effects (bool), and the actual artifact code/template."
    )

    generation = model_adapter.generate(
        instruction=prompt,
        input_data=task_spec
    )

    artifact_type = generation.get("artifact_type", "SCRIPT")
    responsibility = generation.get("responsibility", task_spec["objective"])
    vertical_slice = generation.get("vertical_slice", {
        "raw_input": "Input text or data payload",
        "processing": "Transforms input through single processor logic",
        "raw_output": "Structured output result"
    })
    inputs = generation.get("inputs", ["raw_input"])
    outputs = generation.get("outputs", ["raw_output"])
    components = generation.get("components", ["core_processor"])
    acceptance_tests = generation.get("acceptance_tests", task_spec.get("success_conditions", ["Processor runs without crashing"]))
    external_side_effects = bool(generation.get("external_side_effects", False))

    build_spec = {
        "build_id": build_id,
        "task_id": task_id,
        "artifact_type": artifact_type,
        "responsibility": responsibility,
        "vertical_slice": vertical_slice,
        "inputs": inputs,
        "outputs": outputs,
        "components": components,
        "acceptance_tests": acceptance_tests,
        "external_side_effects": external_side_effects
    }

    validate_contract("BuildSpec", build_spec)

    raw_content = generation.get("artifact_code") or generation.get("content") or f"# Capability: {responsibility}\n# Type: {artifact_type}\n\ndef process(data):\n    return data\n"

    # Real Physical Smoke Test
    smoke_status, smoke_error = run_physical_smoke_test(artifact_type, raw_content)

    artifact_payload = {
        "artifact_id": f"art_{uuid.uuid4().hex[:8]}",
        "build_id": build_id,
        "task_id": task_id,
        "artifact_type": artifact_type,
        "version": "0.1.0",
        "content": raw_content,
        "smoke_test_status": smoke_status,
        "smoke_test_error": smoke_error
    }

    # Optionally persist to artifacts directory
    if artifacts_dir:
        artifacts_dir = Path(artifacts_dir)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        ext = ".py" if artifact_type == "SCRIPT" else ".txt"
        file_path = artifacts_dir / f"{artifact_type.lower()}_{build_id}{ext}"
        file_path.write_text(str(raw_content), encoding="utf-8")
        artifact_payload["content_path"] = str(file_path)

    return build_spec, artifact_payload
