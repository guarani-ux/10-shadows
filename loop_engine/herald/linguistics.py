import re
from typing import List, Tuple


class AntiAILinguisticGuard:
    """
    Shadow 3 (The Herald) Linguistic Integrity Engine.

    Enforces human, conversational spoken English:
    1. Zero em-dashes (—) or en-dashes (–) used as punctuation.
    2. Banned vocabulary list: 'delve', 'tapestry', 'seamlessly', 'testament', 'revolutionize', etc.
    3. Spoken sentence length constraints (< 25 words per sentence for breathability).
    """

    BANNED_WORDS = {
        "delve",
        "delving",
        "delves",
        "tapestry",
        "tapestries",
        "seamlessly",
        "seamless",
        "testament",
        "revolutionize",
        "revolutionizing",
        "revolutionized",
        "beacon",
        "game-changer",
        "gamechanger",
        "furthermore",
        "moreover",
        "in conclusion",
        "in a world where",
        "let's dive in",
        "without further ado",
    }

    @classmethod
    def validate_text(cls, text: str) -> Tuple[bool, List[str]]:
        """
        Scans text for em-dashes, banned AI vocabulary, and non-spoken robotic structures.
        Returns (is_valid, list_of_violations).
        """
        violations = []
        if not text:
            return True, []

        # 1. Em-dash & En-dash scan
        if "—" in text or "–" in text:
            violations.append(
                "Violation: Em-dash ('—') or en-dash ('–') detected. People speak with natural pauses (commas, periods, ellipses), not em-dashes."
            )

        # 2. Banned vocabulary scan (case-insensitive word boundary match)
        for word in cls.BANNED_WORDS:
            pattern = rf"\b{re.escape(word)}\b"
            if re.search(pattern, text, re.IGNORECASE):
                violations.append(
                    f"Violation: Banned AI-speak word '{word}' detected. Replace with natural, plainspoken language."
                )

        # 3. Spoken sentence length scan
        sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
        for idx, sentence in enumerate(sentences, 1):
            words = sentence.split()
            if len(words) > 28:
                violations.append(
                    f"Violation: Sentence {idx} has {len(words)} words ('{' '.join(words[:5])}...'). "
                    f"Spoken dialogue must be under 28 words per breath unit."
                )

        return len(violations) == 0, violations
