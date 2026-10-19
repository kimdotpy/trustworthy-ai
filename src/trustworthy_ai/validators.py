"""
Output Guardrail Validators
Schema Validation, Groundedness Validation, Sensitive Information Detection
"""

import re
import json
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass
from enum import Enum


class ValidationStatus(Enum):
    """Status of a validation check"""
    VALID = "valid"
    INVALID = "invalid"
    WARNING = "warning"


@dataclass
class ValidationResult:
    """Result of a validation operation"""
    status: ValidationStatus
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    corrected_output: Optional[Any] = None


class SchemaValidator:
    """
    Validates that generated responses conform to a predefined schema.

    Approach: Type checking and structure validation.
    Limitations:
    - Cannot validate semantic correctness
    - May be too strict for flexible outputs
    - Complex nested validations can be slow
    """

    def __init__(self, schema: Dict[str, Any]):
        """
        Initialize with a schema definition.

        Schema format:
        {
            "field_name": {
                "type": "string|int|float|bool|list|dict",
                "required": True/False,
                "min_length": int (for strings),
                "max_length": int (for strings),
                "min_value": number (for numbers),
                "max_value": number (for numbers),
                "allowed_values": [list of allowed values],
                "nested_schema": {...} (for dict type)
            }
        }
        """
        self.schema = schema

    def validate(self, response: Dict[str, Any]) -> ValidationResult:
        """
        Validate response against schema.

        Args:
            response: Generated response to validate

        Returns:
            ValidationResult with validation status and errors
        """
        errors = []
        warnings = []

        # Check required fields
        for field_name, field_spec in self.schema.items():
            if field_spec.get("required", False) and field_name not in response:
                errors.append(f"Required field '{field_name}' is missing")

        # Validate present fields
        for field_name, value in response.items():
            if field_name not in self.schema:
                warnings.append(f"Unexpected field '{field_name}' not in schema")
                continue

            field_spec = self.schema[field_name]
            field_errors = self._validate_field(field_name, value, field_spec)
            errors.extend(field_errors)

        is_valid = len(errors) == 0
        status = ValidationStatus.VALID if is_valid else ValidationStatus.INVALID

        if warnings and is_valid:
            status = ValidationStatus.WARNING

        return ValidationResult(
            status=status,
            is_valid=is_valid,
            errors=errors,
            warnings=warnings
        )

    def _validate_field(self, field_name: str, value: Any, spec: Dict[str, Any]) -> List[str]:
        """Validate a single field against its specification"""
        errors = []
        expected_type = spec.get("type", "string")

        # Type validation
        type_map = {
            "string": str,
            "int": int,
            "float": (int, float),
            "bool": bool,
            "list": list,
            "dict": dict,
        }

        expected_python_type = type_map.get(expected_type)
        if expected_python_type and not isinstance(value, expected_python_type):
            errors.append(f"Field '{field_name}' should be {expected_type}, got {type(value).__name__}")
            return errors

        # String validations
        if expected_type == "string" and isinstance(value, str):
            if "min_length" in spec and len(value) < spec["min_length"]:
                errors.append(f"Field '{field_name}' too short (min: {spec['min_length']})")
            if "max_length" in spec and len(value) > spec["max_length"]:
                errors.append(f"Field '{field_name}' too long (max: {spec['max_length']})")

        # Number validations
        if expected_type in ["int", "float"] and isinstance(value, (int, float)):
            if "min_value" in spec and value < spec["min_value"]:
                errors.append(f"Field '{field_name}' below minimum (min: {spec['min_value']})")
            if "max_value" in spec and value > spec["max_value"]:
                errors.append(f"Field '{field_name}' above maximum (max: {spec['max_value']})")

        # Allowed values
        if "allowed_values" in spec and value not in spec["allowed_values"]:
            errors.append(f"Field '{field_name}' has invalid value. Allowed: {spec['allowed_values']}")

        # Nested schema validation
        if expected_type == "dict" and "nested_schema" in spec:
            nested_validator = SchemaValidator(spec["nested_schema"])
            nested_result = nested_validator.validate(value)
            errors.extend([f"{field_name}.{e}" for e in nested_result.errors])

        return errors


class GroundednessValidator:
    """
    Validates that generated claims are supported by reference information.

    Approach: Keyword and fact extraction with cross-reference checking.
    Limitations:
    - Cannot understand complex semantic relationships
    - May miss paraphrased or inferred information
    - Struggles with negations and conditional statements
    """

    def __init__(self, reference_documents: List[str]):
        """
        Initialize with reference documents.

        Args:
            reference_documents: List of reference texts to check against
        """
        self.reference_documents = reference_documents
        self.reference_text = " ".join(reference_documents).lower()

    def validate(self, response: str) -> ValidationResult:
        """
        Validate that response claims are grounded in references.

        Args:
            response: Generated response to validate

        Returns:
            ValidationResult with groundedness check results
        """
        errors = []
        warnings = []

        # Extract factual claims from response
        claims = self._extract_claims(response)

        for claim in claims:
            if not self._is_claim_supported(claim):
                errors.append(f"Unsupported claim: '{claim}'")

        # Check for hedging language that might indicate uncertainty
        hedging_phrases = ['might', 'possibly', 'perhaps', 'unclear', 'not certain']
        for phrase in hedging_phrases:
            if phrase in response.lower():
                warnings.append(f"Response contains uncertain language: '{phrase}'")

        is_valid = len(errors) == 0
        status = ValidationStatus.VALID if is_valid else ValidationStatus.INVALID

        if warnings and is_valid:
            status = ValidationStatus.WARNING

        return ValidationResult(
            status=status,
            is_valid=is_valid,
            errors=errors,
            warnings=warnings
        )

    def _extract_claims(self, text: str) -> List[str]:
        """Extract factual claims from text (simplified approach)"""
        # Split by sentence
        sentences = re.split(r'[.!?]+', text)

        # Filter out questions and non-factual statements
        claims = []
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Skip questions
            if sentence.endswith('?'):
                continue

            # Skip very short sentences
            if len(sentence.split()) < 4:
                continue

            # Simple heuristic: sentences with specific patterns are claims
            if any(indicator in sentence.lower() for indicator in ['is', 'are', 'was', 'were', 'has', 'have']):
                claims.append(sentence)

        return claims

    def _is_claim_supported(self, claim: str) -> bool:
        """Check if a claim is supported by reference documents"""
        claim_lower = claim.lower()

        # Extract key terms from claim (nouns, specific values)
        # Remove common words
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'has', 'have', 'in', 'on', 'at', 'to', 'for'}
        claim_words = [w for w in claim_lower.split() if w not in stop_words and len(w) > 2]

        # Check if most key terms appear in reference
        if not claim_words:
            return True  # No specific claims to verify

        matches = sum(1 for word in claim_words if word in self.reference_text)
        match_ratio = matches / len(claim_words)

        # Require at least 60% of key terms to be present
        return match_ratio >= 0.6


class SensitiveInfoDetector:
    """
    Detects PII or sensitive information in generated outputs.

    Approach: Pattern matching similar to input PII detection.
    Limitations:
    - Same limitations as PIIDetector
    - May not catch generated sensitive context without explicit patterns
    """

    def __init__(self):
        from .detectors import PIIDetector
        self.pii_detector = PIIDetector()

        # Additional patterns for output-specific concerns
        self.sensitive_patterns = [
            r'password\s*:\s*\S+',
            r'api[_-]?key\s*:\s*\S+',
            r'secret\s*:\s*\S+',
            r'token\s*:\s*\S+',
            r'private[_-]?key',
        ]

    def detect(self, output: str) -> ValidationResult:
        """
        Detect sensitive information in output.

        Args:
            output: Generated output to scan

        Returns:
            ValidationResult indicating if sensitive info was found
        """
        errors = []
        warnings = []

        # Check for PII
        pii_result = self.pii_detector.detect(output)
        if pii_result.is_flagged:
            for match in pii_result.matches:
                errors.append(f"Output contains PII ({match.pii_type.value}): {match.value}")

        # Check for credentials/secrets
        for pattern in self.sensitive_patterns:
            matches = re.finditer(pattern, output, re.IGNORECASE)
            for match in matches:
                errors.append(f"Output contains potential secret: {match.group()}")

        is_valid = len(errors) == 0
        status = ValidationStatus.VALID if is_valid else ValidationStatus.INVALID

        corrected_output = None
        if not is_valid and pii_result.redacted_text:
            corrected_output = pii_result.redacted_text

        return ValidationResult(
            status=status,
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            corrected_output=corrected_output
        )
