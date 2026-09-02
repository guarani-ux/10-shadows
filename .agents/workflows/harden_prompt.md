# WORKFLOW — ADVERSARIAL PROMPT HARDENING

## Purpose
Convert raw, ambiguous, or conceptual operator requests into verified, falsifiable Vertical Slice execution prompts before any engineering cycle starts.

## Execution Sequence
1. Intercept the operator's prompt.
2. Delegate to the `adversarial_prompt_compiler` subagent or activate the `adversarial-prompt-compiler` skill.
3. Perform the 4-step interrogation:
   - Identify actual physical intent.
   - Expose hidden assumptions and cheating vectors.
   - Lock down boundary invariants.
   - Formulate the RED falsification test.
4. Output the compiled **Vertical Slice Prompt**.
5. Operator confirms or adjusts the compiled prompt before dispatching to `ts run`.
