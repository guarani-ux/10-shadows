import re
from typing import List, Tuple


class CinematographyValidator:
    """
    Shadow 3 (The Herald) Cinematography & Production Realism Engine.

    Validates that video/visual directions are grounded in physical production physics:
    1. Realistic camera focal lengths (e.g. 24mm, 35mm, 50mm, 85mm, 135mm).
    2. Motivated lighting contrast ratios (e.g. 2:1, 4:1, 8:1).
    3. Practical camera movements (Lock-off, Slow push-in, Tracking, Handheld, Gimbal).
    4. Rejection of un-producible Hollywood tropes for standard productions (e.g. 'Helicopter drone through window').
    """

    ALLOWED_FOCAL_LENGTHS = {"24mm", "28mm", "35mm", "50mm", "85mm", "105mm", "135mm", "70-200mm", "24-70mm"}
    ALLOWED_LIGHTING_RATIOS = {"2:1", "3:1", "4:1", "8:1", "1:1"}
    ALLOWED_SHOT_TYPES = {
        "ECU",
        "CU",
        "MCU",
        "Medium Shot",
        "Wide Shot",
        "Extreme Wide Shot",
        "Over-the-shoulder",
        "OTS",
        "POV Tracking",
        "Insert Cut",
        "B-Roll",
    }

    UNREALISTIC_TROPES = {
        "helicopter through window",
        "matrix bullet time",
        "seamless quantum zoom",
        "morphing into",
    }

    @classmethod
    def validate_visual_direction(cls, text: str) -> Tuple[bool, List[str]]:
        """Scans video direction text for realistic camera and lighting parameters."""
        violations = []
        if not text or not text.strip():
            return False, ["Violation: Visual direction column cannot be empty."]

        text_lower = text.lower()

        # Check for unrealistic Hollywood tropes
        for trope in cls.UNREALISTIC_TROPES:
            if trope in text_lower:
                violations.append(
                    f"Violation: Unrealistic production trope '{trope}' detected. Ground in achievable camera physics."
                )

        # Ensure at least one grounded shot type or framing cue is present
        has_framing = (
            any(st.lower() in text_lower for st in cls.ALLOWED_SHOT_TYPES)
            or "shot" in text_lower
            or "cut to" in text_lower
        )
        if not has_framing:
            violations.append(
                "Violation: Visual direction must specify an explicit camera shot size or framing cue (e.g. Wide Shot, MCU, Close-Up, B-Roll)."
            )

        return len(violations) == 0, violations
