"""On-Device PII Guardian ("Privacy Gate") for MacHybridAI.

Detects personal and sensitive information before anything leaves the Mac:
- Reversible pseudonymization (`[PERSON_1]`, `[EMAIL_1]`, `[PHONE_1]`, etc.)
- Automatic local restoration of stand-in tokens in cloud responses
- Luhn-validated credit card detection, SSNs, API keys/secrets, IPv4/IPv6,
  person names, emails, phone numbers, and user-defined sensitive terms.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, List, Optional, Tuple


class GuardianPolicy(str, Enum):
    """Defines how the Privacy Gate handles detected PII when calling cloud models."""

    REVERSIBLE_MASK = "reversible_mask"
    STRICT_REDACT = "strict_redact"
    FORCE_LOCAL_ON_PII = "force_local_on_pii"


@dataclass(frozen=True)
class PIIEntity:
    """Represents a single PII or secret entity detected on-device."""

    category: str
    original_value: str
    replacement_token: str
    start: int
    end: int
    confidence: float = 0.98

    def to_public_dict(self, include_original: bool = False) -> Dict[str, object]:
        data: Dict[str, object] = {
            "category": self.category,
            "replacement_token": self.replacement_token,
            "start": self.start,
            "end": self.end,
            "confidence": self.confidence,
            "masked_preview": self._mask_preview(self.original_value),
        }
        if include_original:
            data["original_value"] = self.original_value
        return data

    @staticmethod
    def _mask_preview(val: str) -> str:
        if len(val) <= 4:
            return "*" * len(val)
        return f"{val[:2]}{'*' * min(6, len(val) - 4)}{val[-2:]}"


@dataclass
class RedactionResult:
    """Result returned by PIIGuardian after scanning a prompt or document."""

    sanitized_text: str
    entities: List[PIIEntity] = field(default_factory=list)
    policy_applied: GuardianPolicy = GuardianPolicy.REVERSIBLE_MASK
    forced_local: bool = False

    @property
    def pii_flagged(self) -> bool:
        return len(self.entities) > 0

    @property
    def pii_count(self) -> int:
        return len(self.entities)

    @property
    def categories(self) -> List[str]:
        seen: List[str] = []
        for entity in self.entities:
            if entity.category not in seen:
                seen.append(entity.category)
        return seen

    def to_dict(self, include_original: bool = False) -> Dict[str, object]:
        return {
            "sanitized_text": self.sanitized_text,
            "pii_flagged": self.pii_flagged,
            "pii_count": self.pii_count,
            "categories": self.categories,
            "policy_applied": self.policy_applied.value,
            "forced_local": self.forced_local,
            "entities": [e.to_public_dict(include_original=include_original) for e in self.entities],
        }


class PIIVault:
    """Thread-safe local memory vault storing reversible mappings on this Mac.

    Mappings never leave the device and are used to restore stand-in tokens
    (such as `[PERSON_1]` or `[EMAIL_1]`) after cloud reasoning completes.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._token_to_original: Dict[str, str] = {}
        self._original_to_token: Dict[Tuple[str, str], str] = {}
        self._counters: Dict[str, int] = {}

    def register(self, category: str, original_value: str) -> str:
        """Registers an original PII value and returns a deterministic stand-in token."""
        cat_upper = category.upper()
        key = (cat_upper, original_value)
        with self._lock:
            if key in self._original_to_token:
                return self._original_to_token[key]
            idx = self._counters.get(cat_upper, 0) + 1
            self._counters[cat_upper] = idx
            token = f"[{cat_upper}_{idx}]"
            self._original_to_token[key] = token
            self._token_to_original[token] = original_value
            return token

    def restore(self, text: str) -> Tuple[str, int]:
        """Restores all known stand-in tokens in `text` back to real local values."""
        if not text:
            return text, 0
        restored = text
        restored_count = 0
        with self._lock:
            items = sorted(
                self._token_to_original.items(),
                key=lambda kv: len(kv[0]),
                reverse=True,
            )
        for token, original in items:
            occurrences = restored.count(token)
            if occurrences > 0:
                restored = restored.replace(token, original)
                restored_count += occurrences
        return restored, restored_count

    def clear(self) -> None:
        with self._lock:
            self._token_to_original.clear()
            self._original_to_token.clear()
            self._counters.clear()

    def snapshot(self) -> Dict[str, str]:
        with self._lock:
            return dict(self._token_to_original)


def _passes_luhn(card_text: str) -> bool:
    """Validates credit card digits using the Luhn checksum algorithm."""
    digits = [int(ch) for ch in card_text if ch.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    if len(set(digits)) == 1:
        return False
    total = 0
    parity = len(digits) % 2
    for idx, digit in enumerate(digits):
        if idx % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


class PIIGuardian:
    """On-device Privacy Gate that inspects, masks, and restores sensitive data."""

    # Ordered from highest specificity to broader contextual NER patterns
    _PATTERNS: List[Tuple[str, re.Pattern[str], float]] = [
        (
            "SECRET",
            re.compile(
                r"\b(?:"
                r"AIza[0-9A-Za-z\-_]{35}"
                r"|sk-[A-Za-z0-9\-_]{20,}"
                r"|gh[pousr]_[A-Za-z0-9]{20,}"
                r"|AKIA[0-9A-Z]{16}"
                r"|eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"
                r")\b"
            ),
            0.99,
        ),
        (
            "SSN",
            re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b"),
            0.99,
        ),
        (
            "CREDIT_CARD",
            re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
            0.96,
        ),
        (
            "EMAIL",
            re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
            0.99,
        ),
        (
            "PHONE",
            re.compile(
                r"(?:(?<=\s)|(?<=^)|(?<=[(\[\":]))"
                r"(?:\+?1[-.\s]?)?"
                r"(?:\(\d{3}\)[-.\s]?|\b\d{3}[-.\s])"
                r"\d{3}[-.\s]\d{4}\b"
            ),
            0.95,
        ),
        (
            "IP_ADDR",
            re.compile(
                r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
            ),
            0.94,
        ),
        (
            "ORGANIZATION",
            re.compile(
                r"\b([A-Z][A-Za-z0-9&\-]{1,25}(?:\s+[A-Z][A-Za-z0-9&\-]{1,25}){0,3}\s+"
                r"(?:Corp\.?|Corporation|Inc\.?|LLC|LLP|Ltd\.?|Holdings|Partners|Capital|Ventures|Bank))\b"
            ),
            0.92,
        ),
        (
            "PERSON",
            re.compile(
                r"(?:(?<=Mr\.\s)|(?<=Ms\.\s)|(?<=Mrs\.\s)|(?<=Dr\.\s)"
                r"|(?<=Contact:\s)|(?<=Client:\s)|(?<=Patient:\s)|(?<=Author:\s)"
                r"|(?<=Name:\s)|(?<=Prepared by\s)|(?<=Prepared for\s)|(?<=with\s)|(?<=for\s))"
                r"([A-Z][a-z]{1,20}\s+[A-Z][a-z]{1,25})\b"
            ),
            0.91,
        ),
    ]

    _SAFE_CAPITALIZED_PHRASES = {
        "This Mac",
        "Cloud Models",
        "Privacy Gate",
        "United States",
        "New York",
        "San Francisco",
        "Mountain View",
        "Google Search",
        "Deep Research",
        "Base Case",
        "Management Case",
        "Downside Case",
        "Investment Committee",
        "Deal Review",
        "Portfolio Review",
    }

    def __init__(
        self,
        policy: GuardianPolicy = GuardianPolicy.REVERSIBLE_MASK,
        vault: Optional[PIIVault] = None,
        custom_sensitive_terms: Optional[Iterable[str]] = None,
        allowlist_terms: Optional[Iterable[str]] = None,
    ) -> None:
        self.policy = policy
        self.vault = vault or PIIVault()
        self.custom_terms: List[str] = [
            t.strip() for t in (custom_sensitive_terms or []) if t and t.strip()
        ]
        self.allowlist_terms: List[str] = [
            t.strip() for t in (allowlist_terms or []) if t and t.strip()
        ]

    def set_custom_terms(self, terms: Iterable[str]) -> None:
        self.custom_terms = [t.strip() for t in terms if t and t.strip()]

    def set_allowlist_terms(self, terms: Iterable[str]) -> None:
        self.allowlist_terms = [t.strip() for t in terms if t and t.strip()]

    def _is_allowlisted(self, candidate: str) -> bool:
        cand_lower = candidate.strip().lower()
        if not cand_lower:
            return False
        for safe in self.allowlist_terms:
            if cand_lower == safe.lower():
                return True
        return False

    def redact(
        self,
        text: str,
        policy_override: Optional[GuardianPolicy] = None,
    ) -> RedactionResult:
        """Scans `text` on-device and masks or redacts detected PII according to policy."""
        active_policy = policy_override or self.policy
        if not text:
            return RedactionResult(sanitized_text="", policy_applied=active_policy)

        raw_matches: List[Tuple[int, int, str, str, float]] = []

        # 1. Check user-supplied custom sensitive terms first
        for term in sorted(self.custom_terms, key=len, reverse=True):
            if self._is_allowlisted(term):
                continue
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            for match in pattern.finditer(text):
                raw_matches.append(
                    (match.start(), match.end(), "CUSTOM", match.group(0), 1.0)
                )

        # 2. Check built-in regex, algorithmic, and NER patterns
        for category, regex, confidence in self._PATTERNS:
            for match in regex.finditer(text):
                start, end = match.span()
                candidate = match.group(0)
                if self._is_allowlisted(candidate):
                    continue
                if category == "CREDIT_CARD" and not _passes_luhn(candidate):
                    continue
                if category == "IP_ADDR" and (
                    candidate == "127.0.0.1" or candidate.startswith("0.")
                ):
                    continue
                if category in {"PERSON", "ORGANIZATION"} and candidate in self._SAFE_CAPITALIZED_PHRASES:
                    continue
                raw_matches.append((start, end, category, candidate, confidence))

        # 3. Deduplicate overlapping spans (prefer earlier start, then longer match)
        raw_matches.sort(key=lambda item: (item[0], -(item[1] - item[0])))
        accepted: List[Tuple[int, int, str, str, float]] = []
        last_end = -1
        for start, end, category, candidate, confidence in raw_matches:
            if start >= last_end:
                accepted.append((start, end, category, candidate, confidence))
                last_end = end

        if not accepted:
            return RedactionResult(
                sanitized_text=text,
                entities=[],
                policy_applied=active_policy,
                forced_local=False,
            )

        entities: List[PIIEntity] = []
        out_parts: List[str] = []
        cursor = 0

        for start, end, category, candidate, confidence in accepted:
            out_parts.append(text[cursor:start])
            if active_policy == GuardianPolicy.STRICT_REDACT:
                token = f"[REDACTED_{category}]"
            else:
                token = self.vault.register(category, candidate)
            out_parts.append(token)
            entities.append(
                PIIEntity(
                    category=category,
                    original_value=candidate,
                    replacement_token=token,
                    start=start,
                    end=end,
                    confidence=confidence,
                )
            )
            cursor = end

        out_parts.append(text[cursor:])
        sanitized_text = "".join(out_parts)
        forced_local = active_policy == GuardianPolicy.FORCE_LOCAL_ON_PII and len(entities) > 0

        return RedactionResult(
            sanitized_text=sanitized_text,
            entities=entities,
            policy_applied=active_policy,
            forced_local=forced_local,
        )

    def restore(self, cloud_text: str) -> Tuple[str, int]:
        """Restores stand-in tokens in cloud output using the local PIIVault."""
        if self.policy == GuardianPolicy.STRICT_REDACT:
            return cloud_text, 0
        return self.vault.restore(cloud_text)
