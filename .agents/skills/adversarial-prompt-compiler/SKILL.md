---
name: adversarial-prompt-compiler
description: Adversarially deconstructs raw operator prompts, identifies hidden assumptions, closes cheating surfaces, and compiles them into rigorous, falsifiable Vertical Slice execution prompts.
---

# ADVERSARIAL PROMPT COMPILER SKILL

Activate this skill when the operator submits a raw, conceptual, ambiguous, or complex request and needs it hardened into a precise, falsifiable Ten Shadows execution specification.

## Core Purpose

Transforms:
> *"I want X to do Y and be smart and reliable."*

Into:
1. **Underlying Invariant Definition:** What must become physically true.
2. **Cheating Vector Elimination:** How a model could hallucinate or self-certify false success, and how to block it.
3. **Falsification-First Test Harness:** The exact RED test that must fail before code synthesis.
4. **Minimal Vertical Slice:** The exact scope lock boundary.

## Step-by-Step Hardening Procedure

1. **Epistemic Interrogation:**
   - Detect broad scope, subjective goals, and unstated assumptions.
   - Determine the physical oracle: How will we know with 100% mechanical certainty that this succeeded?
2. **Deficit Identification:**
   - Does this task require an unfamiliar domain model?
   - Does it require external API access or specific data schemas?
   - Flag any `SEMANTIC_BINDING_DEFICIT`, `CAPABILITY_DEFICIT`, or `VERIFIER_DEFICIT`.
3. **Prompt Compilation:**
   - Format the request as a **Vertical Slice Task** adhering strictly to the Ten Shadows Sovereign Execution contract.
