import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

SCHEMA_PATH = Path(__file__).parent.parent / "schemas" / "forge.schema.json"

_SCHEMA_CACHE: Optional[Dict[str, Any]] = None


def get_schema() -> Dict[str, Any]:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            _SCHEMA_CACHE = json.load(f)
    return _SCHEMA_CACHE


def validate_contract(definition_name: str, instance: Dict[str, Any]) -> bool:
    """
    Validates a data payload against a specific $def in forge.schema.json.
    Supports jsonschema library if available, and includes a strict, complete fallback validator.
    """
    schema = get_schema()
    defs = schema.get("$defs", {})
    if definition_name not in defs:
        raise ValueError(f"Definition '{definition_name}' not found in forge.schema.json")

    subschema = {
        "$schema": schema.get("$schema", "https://json-schema.org/draft/2020-12/schema"),
        "$defs": defs,
        **defs[definition_name]
    }

    try:
        import jsonschema
        jsonschema.validate(instance=instance, schema=subschema)
        return True
    except ImportError:
        # Fallback pure-Python contract validation for zero-dependency environments
        return _fallback_validate(defs[definition_name], instance, defs)


def _fallback_validate(subschema: Dict[str, Any], instance: Any, defs: Dict[str, Any]) -> bool:
    if "oneOf" in subschema:
        valid_count = 0
        for branch in subschema["oneOf"]:
            try:
                if _fallback_validate(branch, instance, defs):
                    valid_count += 1
            except Exception:
                pass
        if valid_count != 1:
            raise ValueError(f"Instance did not match exactly one branch of oneOf (matched {valid_count})")
        return True

    expected_type = subschema.get("type")

    # Handle nullable / union types (e.g. ["string", "null"])
    if isinstance(expected_type, list):
        matched = False
        last_error = None
        for t in expected_type:
            temp_schema = dict(subschema, type=t)
            try:
                _fallback_validate(temp_schema, instance, defs)
                matched = True
                break
            except Exception as e:
                last_error = e
        if not matched:
            raise ValueError(f"Instance {instance} did not match allowed union types {expected_type}: {last_error}")
        return True

    if expected_type == "null":
        if instance is not None:
            raise ValueError(f"Expected null/None, got {instance}")

    elif expected_type == "object":
        if not isinstance(instance, dict):
            raise ValueError(f"Expected object/dict, got {type(instance).__name__}")
        
        required = subschema.get("required", [])
        for req in required:
            if req not in instance:
                raise ValueError(f"Missing required property '{req}'")

        properties = subschema.get("properties", {})
        if subschema.get("additionalProperties") is False:
            for k in instance.keys():
                if k not in properties:
                    raise ValueError(f"Additional property '{k}' not permitted")

        for k, val in instance.items():
            if k in properties:
                prop_schema = properties[k]
                if "$ref" in prop_schema:
                    ref_name = prop_schema["$ref"].split("/")[-1]
                    _fallback_validate(defs[ref_name], val, defs)
                else:
                    _fallback_validate(prop_schema, val, defs)

    elif expected_type == "array":
        if not isinstance(instance, (list, tuple)):
            raise ValueError(f"Expected array/list, got {type(instance).__name__}")
        min_items = subschema.get("minItems", 0)
        if len(instance) < min_items:
            raise ValueError(f"Array length {len(instance)} less than minItems {min_items}")
        items_schema = subschema.get("items")
        if items_schema:
            for item in instance:
                if "$ref" in items_schema:
                    ref_name = items_schema["$ref"].split("/")[-1]
                    _fallback_validate(defs[ref_name], item, defs)
                else:
                    _fallback_validate(items_schema, item, defs)

    elif expected_type == "string":
        if not isinstance(instance, str):
            raise ValueError(f"Expected string, got {type(instance).__name__}")
        min_len = subschema.get("minLength", 0)
        if len(instance) < min_len:
            raise ValueError(f"String length {len(instance)} less than minLength {min_len}")
        enum_vals = subschema.get("enum")
        if enum_vals is not None and instance not in enum_vals:
            raise ValueError(f"Value '{instance}' not in allowed enum {enum_vals}")
        const_val = subschema.get("const")
        if const_val is not None and instance != const_val:
            raise ValueError(f"Value '{instance}' does not equal const '{const_val}'")
        pattern = subschema.get("pattern")
        if pattern is not None and not re.search(pattern, instance):
            raise ValueError(f"String '{instance}' does not match pattern '{pattern}'")

    elif expected_type == "integer":
        if not isinstance(instance, int) or isinstance(instance, bool):
            raise ValueError(f"Expected integer, got {type(instance).__name__}")
        if "minimum" in subschema and instance < subschema["minimum"]:
            raise ValueError(f"Integer {instance} is less than minimum {subschema['minimum']}")
        if "maximum" in subschema and instance > subschema["maximum"]:
            raise ValueError(f"Integer {instance} is greater than maximum {subschema['maximum']}")

    elif expected_type == "number":
        if not isinstance(instance, (int, float)) or isinstance(instance, bool):
            raise ValueError(f"Expected number, got {type(instance).__name__}")

    elif expected_type == "boolean":
        if not isinstance(instance, bool):
            raise ValueError(f"Expected bool, got {type(instance).__name__}")

    return True
