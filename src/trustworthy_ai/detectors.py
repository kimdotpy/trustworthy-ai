"""
Input Guardrail Detectors
PII Detection, Prompt Injection Detection, Sensitive Topic Classification
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class PIIType(Enum):
    """Types of PII that can be detected"""
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    PASSPORT = "passport"
    DRIVER_LICENSE = "driver_license"


class SensitiveTopic(Enum):
    """Sensitive topics requiring special handling"""
    MEDICAL = "medical"
    FINANCIAL = "financial"
    LEGAL = "legal"
    POLITICAL = "political"
    VIOLENCE = "violence"
    ADULT_CONTENT = "adult_content"
    HATE_SPEECH = "hate_speech"


@dataclass
class PIIMatch:
    """Represents a detected PII match"""
    pii_type: PIIType
    value: str
    start: int
    end: int
    confidence: float


@dataclass
class DetectionResult:
    """Result of a detection operation"""
    is_flagged: bool
    matches: List[PIIMatch]
    redacted_text: Optional[str] = None
    reason: Optional[str] = None
    confidence: float = 0.0


class PIIDetector:
    """
    Detects and handles personally identifiable information.

    Approach: Regex-based pattern matching for common PII types.
    Limitations:
    - May miss context-dependent PII (names, addresses without clear patterns)
    - International phone/SSN formats may not be covered
    - Can produce false positives on similar-looking patterns
    """

    def __init__(self):
        self.patterns = {
            PIIType.EMAIL: r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            PIIType.PHONE: r'\b(?:\+?1[-.]?)?\(?([0-9]{3})\)?[-.]?([0-9]{3})[-.]?([0-9]{4})\b',
            PIIType.SSN: r'\b\d{3}-\d{2}-\d{4}\b',
            PIIType.CREDIT_CARD: r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
            PIIType.IP_ADDRESS: r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
            PIIType.PASSPORT: r'\b[A-Z]{1,2}\d{6,9}\b',
            PIIType.DRIVER_LICENSE: r'\b[A-Z]{1,2}\d{5,8}\b',
        }

    def detect(self, text: str) -> DetectionResult:
        """
        Detect PII in the given text.

        Args:
            text: Input text to scan

        Returns:
            DetectionResult with all matches found
        """
        matches = []

        for pii_type, pattern in self.patterns.items():
            for match in re.finditer(pattern, text):
                matches.append(PIIMatch(
                    pii_type=pii_type,
                    value=match.group(),
                    start=match.start(),
                    end=match.end(),
                    confidence=0.9  # High confidence for regex matches
                ))

        is_flagged = len(matches) > 0
        redacted_text = self._redact_pii(text, matches) if is_flagged else None

        return DetectionResult(
            is_flagged=is_flagged,
            matches=matches,
            redacted_text=redacted_text,
            reason=f"Detected {len(matches)} PII instance(s)" if is_flagged else None,
            confidence=max([m.confidence for m in matches], default=0.0)
        )

    def _redact_pii(self, text: str, matches: List[PIIMatch]) -> str:
        """Redact PII from text by replacing with placeholders"""
        # Sort matches by position (reverse order to maintain indices)
        sorted_matches = sorted(matches, key=lambda m: m.start, reverse=True)

        redacted = text
        for match in sorted_matches:
            placeholder = f"[{match.pii_type.value.upper()}_REDACTED]"
            redacted = redacted[:match.start] + placeholder + redacted[match.end:]

        return redacted


class PromptInjectionDetector:
    """
    Detects prompt injection attempts.

    Approach: Pattern matching against known injection techniques.
    Limitations:
    - Cannot detect novel/creative injection attempts
    - May miss context-dependent injections
    - Can have false positives on legitimate meta-discussion
    """

    def __init__(self):
        # Common prompt injection patterns
        self.injection_patterns = [
            # Direct instruction override
            r'ignore\s+(all\s+)?(previous|prior|above)\s+instructions?',
            r'disregard\s+(all\s+)?(previous|prior|above)',
            r'forget\s+(all\s+)?(previous|prior|above)',

            # System prompt extraction
            r'(show|print|display|reveal|tell)\s+(me\s+)?(your|the)\s+(system\s+)?(prompt|instructions?)',
            r'what\s+(are|is)\s+(your|the)\s+(system\s+)?(prompt|instructions?)',

            # Role manipulation
            r'you\s+are\s+now\s+a',
            r'act\s+as\s+(if\s+you\s+are\s+)?a',
            r'pretend\s+(you\s+are|to\s+be)\s+a',

            # Constraint bypass
            r'ignore\s+(all\s+)?(rules|constraints|restrictions|guidelines)',
            r'bypass\s+(all\s+)?(rules|constraints|restrictions|safety)',

            # Delimiter/encoding attempts
            r'---\s*END\s+INSTRUCTIONS?',
            r'<\s*/?\s*(system|instructions?|prompt)\s*>',

            # Special commands
            r'sudo\s+mode',
            r'developer\s+mode',
            r'admin\s+mode',
        ]

    def detect(self, text: str) -> DetectionResult:
        """
        Detect prompt injection attempts.

        Args:
            text: User input to analyze

        Returns:
            DetectionResult indicating if injection was detected
        """
        matches = []
        text_lower = text.lower()

        for pattern in self.injection_patterns:
            for match in re.finditer(pattern, text_lower):
                matches.append(PIIMatch(
                    pii_type=PIIType.EMAIL,  # Reusing PIIMatch structure
                    value=match.group(),
                    start=match.start(),
                    end=match.end(),
                    confidence=0.8
                ))

        is_flagged = len(matches) > 0

        # Additional heuristics
        if not is_flagged:
            # Check for multiple command-like patterns
            command_indicators = ['ignore', 'disregard', 'forget', 'show', 'reveal', 'tell me']
            command_count = sum(1 for indicator in command_indicators if indicator in text_lower)

            if command_count >= 3:
                is_flagged = True
                matches.append(PIIMatch(
                    pii_type=PIIType.EMAIL,
                    value="multiple command indicators",
                    start=0,
                    end=0,
                    confidence=0.6
                ))

        return DetectionResult(
            is_flagged=is_flagged,
            matches=matches,
            reason=f"Potential prompt injection detected: {matches[0].value}" if is_flagged else None,
            confidence=max([m.confidence for m in matches], default=0.0)
        )


class SensitiveTopicClassifier:
    """
    Classifies text for sensitive topics requiring special handling.

    Approach: Keyword and pattern-based classification.
    Limitations:
    - Cannot understand context or intent
    - May miss euphemisms or coded language
    - Can flag legitimate educational/medical content
    """

    def __init__(self):
        self.topic_keywords = {
            SensitiveTopic.MEDICAL: [
                'diagnosis', 'prescription', 'medication', 'surgery', 'treatment',
                'doctor', 'hospital', 'patient', 'symptoms', 'disease', 'illness'
            ],
            SensitiveTopic.FINANCIAL: [
                'invest', 'stock', 'trading', 'loan', 'mortgage', 'credit',
                'bankruptcy', 'tax advice', 'financial advice', 'portfolio'
            ],
            SensitiveTopic.LEGAL: [
                'lawsuit', 'legal advice', 'attorney', 'court', 'sue',
                'contract review', 'rights', 'liability', 'lawyer'
            ],
            SensitiveTopic.POLITICAL: [
                'election', 'vote', 'candidate', 'political party',
                'legislation', 'government policy', 'protest'
            ],
            SensitiveTopic.VIOLENCE: [
                'harm', 'kill', 'weapon', 'attack', 'assault', 'murder',
                'suicide', 'self-harm', 'bomb', 'explosive'
            ],
            SensitiveTopic.ADULT_CONTENT: [
                'explicit', 'nsfw', 'adult content', 'sexual', 'pornography'
            ],
            SensitiveTopic.HATE_SPEECH: [
                'hate speech', 'racist', 'discrimination', 'slur',
                'bigotry', 'supremacy'
            ],
        }

        # Actions to take for each topic
        self.topic_actions = {
            SensitiveTopic.MEDICAL: "WARN",
            SensitiveTopic.FINANCIAL: "WARN",
            SensitiveTopic.LEGAL: "WARN",
            SensitiveTopic.POLITICAL: "LOG",
            SensitiveTopic.VIOLENCE: "BLOCK",
            SensitiveTopic.ADULT_CONTENT: "BLOCK",
            SensitiveTopic.HATE_SPEECH: "BLOCK",
        }

    def classify(self, text: str) -> Tuple[List[SensitiveTopic], str]:
        """
        Classify text for sensitive topics.

        Args:
            text: Input text to classify

        Returns:
            Tuple of (detected topics, recommended action)
        """
        text_lower = text.lower()
        detected_topics = []

        for topic, keywords in self.topic_keywords.items():
            # Count keyword matches
            matches = sum(1 for keyword in keywords if keyword in text_lower)

            # Flag if multiple keywords match
            if matches >= 2:
                detected_topics.append(topic)

        # Determine strictest action needed
        action = "ALLOW"
        if detected_topics:
            actions = [self.topic_actions[topic] for topic in detected_topics]
            if "BLOCK" in actions:
                action = "BLOCK"
            elif "WARN" in actions:
                action = "WARN"
            else:
                action = "LOG"

        return detected_topics, action
