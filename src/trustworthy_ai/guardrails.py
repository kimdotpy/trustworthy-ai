"""
Main Guardrail Pipeline
Orchestrates input and output guardrails
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .detectors import (
    PIIDetector,
    PromptInjectionDetector,
    SensitiveTopicClassifier,
    DetectionResult,
    SensitiveTopic,
)
from .validators import (
    SchemaValidator,
    GroundednessValidator,
    SensitiveInfoDetector,
    ValidationResult,
    ValidationStatus,
)


class GuardrailAction(Enum):
    """Actions that can be taken when guardrails are triggered"""
    ALLOW = "allow"
    REDACT = "redact"
    BLOCK = "block"
    WARN = "warn"
    REGENERATE = "regenerate"
    FALLBACK = "fallback"


@dataclass
class GuardrailResult:
    """Result of applying guardrails"""
    action: GuardrailAction
    passed: bool
    original_input: Optional[str] = None
    processed_input: Optional[str] = None
    original_output: Optional[Any] = None
    processed_output: Optional[Any] = None
    flags: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class InputGuardrails:
    """
    Applies input guardrails to user requests.

    Components:
    - PII Detection and redaction
    - Prompt injection detection
    - Sensitive topic classification
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize input guardrails.

        Args:
            config: Configuration options
                - redact_pii: bool (default True)
                - block_prompt_injection: bool (default True)
                - sensitive_topic_actions: dict mapping topics to actions
        """
        self.config = config or {}
        self.pii_detector = PIIDetector()
        self.injection_detector = PromptInjectionDetector()
        self.topic_classifier = SensitiveTopicClassifier()

        self.redact_pii = self.config.get("redact_pii", True)
        self.block_injection = self.config.get("block_prompt_injection", True)

    def apply(self, user_input: str) -> GuardrailResult:
        """
        Apply all input guardrails to user input.

        Args:
            user_input: Raw user input

        Returns:
            GuardrailResult with action and processed input
        """
        flags = []
        warnings = []
        processed_input = user_input
        action = GuardrailAction.ALLOW
        metadata = {}

        # 1. PII Detection
        pii_result = self.pii_detector.detect(user_input)
        if pii_result.is_flagged:
            flags.append(f"PII detected: {len(pii_result.matches)} instance(s)")
            metadata["pii_detected"] = [
                {
                    "type": m.pii_type.value,
                    "value": m.value[:10] + "...",  # Truncate for logging
                    "confidence": m.confidence
                }
                for m in pii_result.matches
            ]

            if self.redact_pii:
                processed_input = pii_result.redacted_text
                warnings.append("PII has been redacted from input")

        # 2. Prompt Injection Detection
        injection_result = self.injection_detector.detect(user_input)
        if injection_result.is_flagged:
            flags.append(f"Prompt injection detected: {injection_result.reason}")
            metadata["injection_confidence"] = injection_result.confidence

            if self.block_injection:
                action = GuardrailAction.BLOCK
                return GuardrailResult(
                    action=action,
                    passed=False,
                    original_input=user_input,
                    processed_input=None,
                    flags=flags,
                    warnings=warnings,
                    metadata=metadata
                )

        # 3. Sensitive Topic Classification
        topics, topic_action = self.topic_classifier.classify(user_input)
        if topics:
            flags.append(f"Sensitive topics detected: {[t.value for t in topics]}")
            metadata["sensitive_topics"] = [t.value for t in topics]
            metadata["recommended_action"] = topic_action

            if topic_action == "BLOCK":
                action = GuardrailAction.BLOCK
                return GuardrailResult(
                    action=action,
                    passed=False,
                    original_input=user_input,
                    processed_input=None,
                    flags=flags,
                    warnings=warnings,
                    metadata=metadata
                )
            elif topic_action == "WARN":
                warnings.append(f"Sensitive topics: {', '.join([t.value for t in topics])}")

        # If we made it here, input is allowed (possibly with redactions)
        if processed_input != user_input:
            action = GuardrailAction.REDACT

        return GuardrailResult(
            action=action,
            passed=True,
            original_input=user_input,
            processed_input=processed_input,
            flags=flags,
            warnings=warnings,
            metadata=metadata
        )


class OutputGuardrails:
    """
    Applies output guardrails to generated responses.

    Components:
    - Schema validation
    - Groundedness validation
    - Sensitive information detection
    """

    def __init__(
        self,
        schema: Optional[Dict[str, Any]] = None,
        reference_documents: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize output guardrails.

        Args:
            schema: Schema definition for response validation
            reference_documents: Reference docs for groundedness checking
            config: Configuration options
                - validate_schema: bool (default True if schema provided)
                - check_groundedness: bool (default True if references provided)
                - block_sensitive_output: bool (default True)
                - regenerate_on_fail: bool (default False)
        """
        self.config = config or {}
        self.schema = schema
        self.reference_documents = reference_documents or []

        self.schema_validator = SchemaValidator(schema) if schema else None
        self.groundedness_validator = (
            GroundednessValidator(reference_documents) if reference_documents else None
        )
        self.sensitive_detector = SensitiveInfoDetector()

        self.validate_schema = self.config.get("validate_schema", schema is not None)
        self.check_groundedness = self.config.get("check_groundedness", bool(reference_documents))
        self.block_sensitive = self.config.get("block_sensitive_output", True)
        self.regenerate_on_fail = self.config.get("regenerate_on_fail", False)

    def apply(self, generated_output: Any, output_type: str = "text") -> GuardrailResult:
        """
        Apply all output guardrails to generated response.

        Args:
            generated_output: Generated response (string or dict)
            output_type: Type of output ("text" or "structured")

        Returns:
            GuardrailResult with validation results
        """
        flags = []
        warnings = []
        processed_output = generated_output
        action = GuardrailAction.ALLOW
        metadata = {}

        # 1. Schema Validation (for structured output)
        if output_type == "structured" and self.validate_schema and self.schema_validator:
            if isinstance(generated_output, dict):
                schema_result = self.schema_validator.validate(generated_output)

                if not schema_result.is_valid:
                    flags.append(f"Schema validation failed: {', '.join(schema_result.errors)}")
                    metadata["schema_errors"] = schema_result.errors

                    if self.regenerate_on_fail:
                        action = GuardrailAction.REGENERATE
                    else:
                        action = GuardrailAction.FALLBACK

                    return GuardrailResult(
                        action=action,
                        passed=False,
                        original_output=generated_output,
                        processed_output=None,
                        flags=flags,
                        warnings=warnings,
                        metadata=metadata
                    )

                if schema_result.warnings:
                    warnings.extend(schema_result.warnings)

        # 2. Groundedness Validation (for text output)
        if output_type == "text" and self.check_groundedness and self.groundedness_validator:
            if isinstance(generated_output, str):
                groundedness_result = self.groundedness_validator.validate(generated_output)

                if not groundedness_result.is_valid:
                    flags.append(f"Groundedness check failed: {len(groundedness_result.errors)} unsupported claim(s)")
                    metadata["groundedness_errors"] = groundedness_result.errors

                    if self.regenerate_on_fail:
                        action = GuardrailAction.REGENERATE
                        warnings.append("Response contains unsupported claims - regeneration recommended")
                    else:
                        warnings.append("Response may contain unsupported claims")

                if groundedness_result.warnings:
                    warnings.extend(groundedness_result.warnings)

        # 3. Sensitive Information Detection
        output_text = generated_output if isinstance(generated_output, str) else str(generated_output)
        sensitive_result = self.sensitive_detector.detect(output_text)

        if not sensitive_result.is_valid:
            flags.append(f"Sensitive information in output: {len(sensitive_result.errors)} issue(s)")
            metadata["sensitive_errors"] = sensitive_result.errors

            if self.block_sensitive:
                if sensitive_result.corrected_output:
                    action = GuardrailAction.REDACT
                    processed_output = sensitive_result.corrected_output
                    warnings.append("Sensitive information has been redacted from output")
                else:
                    action = GuardrailAction.BLOCK
                    return GuardrailResult(
                        action=action,
                        passed=False,
                        original_output=generated_output,
                        processed_output=None,
                        flags=flags,
                        warnings=warnings,
                        metadata=metadata
                    )

        # If we made it here, output is valid (possibly with modifications)
        return GuardrailResult(
            action=action,
            passed=True,
            original_output=generated_output,
            processed_output=processed_output,
            flags=flags,
            warnings=warnings,
            metadata=metadata
        )


class GuardrailPipeline:
    """
    Complete guardrail pipeline for an AI application.
    Orchestrates input and output guardrails.
    """

    def __init__(
        self,
        input_config: Optional[Dict[str, Any]] = None,
        output_config: Optional[Dict[str, Any]] = None,
        schema: Optional[Dict[str, Any]] = None,
        reference_documents: Optional[List[str]] = None
    ):
        """
        Initialize guardrail pipeline.

        Args:
            input_config: Configuration for input guardrails
            output_config: Configuration for output guardrails
            schema: Schema for output validation
            reference_documents: Reference docs for groundedness
        """
        self.input_guardrails = InputGuardrails(input_config)
        self.output_guardrails = OutputGuardrails(schema, reference_documents, output_config)
        self.audit_log: List[GuardrailResult] = []

    def process_input(self, user_input: str) -> Tuple[bool, GuardrailResult]:
        """
        Process user input through input guardrails.

        Returns:
            Tuple of (should_proceed, result)
        """
        result = self.input_guardrails.apply(user_input)
        self.audit_log.append(result)
        return result.passed, result

    def process_output(self, generated_output: Any, output_type: str = "text") -> Tuple[bool, GuardrailResult]:
        """
        Process generated output through output guardrails.

        Returns:
            Tuple of (should_return, result)
        """
        result = self.output_guardrails.apply(generated_output, output_type)
        self.audit_log.append(result)
        return result.passed, result

    def get_audit_log(self) -> List[GuardrailResult]:
        """Get the complete audit log of guardrail checks"""
        return self.audit_log.copy()
