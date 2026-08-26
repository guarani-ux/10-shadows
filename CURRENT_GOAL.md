# Current Mission: Intelligent AV Script Generation Engine (Shadow 3 - The Herald)

## Objective
Implement an industrial-grade, 3-section Audio-Visual (AV) script generator that integrates:
1. **Section 1:** Organizational Goal Alignment & Strategic Audience Persona.
2. **Section 2:** Production Constraints, WPM Pacing Ceiling, and Modular Cut-Down Sub-parts (Shorts/Reels).
3. **Section 3:** Master 3-Column AV Script Table (Section/Timecode | Spoken Human Audio | Cinematographic Video & B-Roll).

## Hard Invariants & Anti-AI Linguistic Guard
1. **Zero AI Speak:** Strictly ban em-dashes (`—`), "delve", "tapestry", "seamlessly", "testament", "revolutionize".
2. **Spoken Cadence Synchronization:** Dialogue word count must mathematically fit shot duration (`words <= duration * (target_wpm / 60)`).
3. **Realistic Cinematography:** Video column must use physical camera focal lengths (`24mm`, `85mm`), lighting ratios (`2:1`, `4:1`), and motivated B-roll cuts grounded in real production SOPs.
4. **Zero-Trust Execution:** All candidate scripts generated and verified inside ephemeral Git worktree sandboxes.
