"""
Evaluation Report Generator
Generates comprehensive evaluation reports for the guardrail system
"""

import json
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path


class EvaluationReportGenerator:
    """Generates detailed evaluation reports with metrics and analysis"""

    def __init__(self, test_results_path: str):
        """
        Initialize report generator.

        Args:
            test_results_path: Path to test results JSON file
        """
        with open(test_results_path, 'r') as f:
            self.data = json.load(f)

        self.results = self.data['results']
        self.test_cases = self.data['test_cases']

    def generate_markdown_report(self, output_path: str):
        """Generate comprehensive markdown report"""
        report = []

        # Header
        report.append("# Guardrail System Evaluation Report")
        report.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"\n**Total Test Cases:** {self.results['total_tests']}")
        report.append("\n---\n")

        # Executive Summary
        report.append("## Executive Summary\n")
        report.append(f"- **Pass Rate:** {self.results['pass_rate']:.1%}")
        report.append(f"- **Precision:** {self.results['precision']:.2%}")
        report.append(f"- **Recall:** {self.results['recall']:.2%}")
        report.append(f"- **F1 Score:** {self.results['f1_score']:.2%}")
        report.append(f"- **Accuracy:** {self.results['accuracy']:.2%}\n")

        # Detailed Metrics
        report.append("## Detailed Metrics\n")
        report.append("### Classification Metrics\n")
        report.append(f"- True Positives: {self.results['true_positives']}")
        report.append(f"- True Negatives: {self.results['true_negatives']}")
        report.append(f"- False Positives: {self.results['false_positives']}")
        report.append(f"- False Negatives: {self.results['false_negatives']}\n")

        # Performance by Category
        report.append("### Performance by Category\n")
        report.append("| Category | Passed | Total | Success Rate |")
        report.append("|----------|--------|-------|--------------|")
        for category, stats in self.results['by_category'].items():
            rate = stats['passed'] / stats['total'] if stats['total'] > 0 else 0
            report.append(f"| {category} | {stats['passed']} | {stats['total']} | {rate:.1%} |")
        report.append("")

        # Failed Test Cases
        report.append("## Failed Test Cases\n")
        failed_tests = [tc for tc in self.test_cases if not tc['passed']]
        if failed_tests:
            for tc in failed_tests:
                report.append(f"### [{tc['id']}] {tc['description']}\n")
                report.append(f"- **Category:** {tc['category']}")
                report.append(f"- **Expected:** {tc['expected_action']}, Should Pass: {tc['should_pass']}")
                report.append(f"- **Actual:** {tc['actual_action']}")
                report.append(f"- **Flags:** {', '.join(tc['actual_flags']) if tc['actual_flags'] else 'None'}")
                if tc['notes']:
                    report.append(f"- **Notes:** {tc['notes']}")
                report.append("")
        else:
            report.append("No failed test cases.\n")

        # Failure Analysis
        report.append("## Failure Analysis\n")
        report.append(self._generate_failure_analysis())

        # Guardrail Trade-offs
        report.append("\n## Guardrail Trade-offs\n")
        report.append(self._generate_tradeoff_analysis())

        # Limitations
        report.append("\n## Implementation Limitations\n")
        report.append(self._generate_limitations())

        # Risk Assessment
        report.append("\n## Risk Assessment\n")
        report.append(self._generate_risk_assessment())

        # Recommendations
        report.append("\n## Recommendations\n")
        report.append(self._generate_recommendations())

        # Write report
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report))

        print(f"Markdown report generated: {output_path}")

    def _generate_failure_analysis(self) -> str:
        """Generate failure analysis section"""
        analysis = []

        failed = [tc for tc in self.test_cases if not tc['passed']]

        if not failed:
            return "All tests passed. No failure analysis required.\n"

        analysis.append("### Identified Failure Cases\n")

        # Analyze false positives
        fp_cases = [tc for tc in failed if tc['should_pass'] and not tc['passed']]
        if fp_cases:
            analysis.append("#### False Positives (Legitimate requests incorrectly blocked)\n")
            for tc in fp_cases[:2]:  # Limit to 2 examples
                analysis.append(f"**Case: {tc['id']} - {tc['description']}**")
                analysis.append(f"- Input/Output: `{tc.get('input_text') or str(tc.get('output_data'))[:100]}`")
                analysis.append(f"- Why it failed: The guardrail was too strict. Pattern-based detection flagged legitimate content.")
                analysis.append(f"- Consequences: Reduced usability; legitimate users may be frustrated.")
                analysis.append(f"- Improvement: Use contextual analysis or machine learning models instead of rigid patterns.\n")

        # Analyze false negatives
        fn_cases = [tc for tc in failed if not tc['should_pass'] and tc['passed']]
        if fn_cases:
            analysis.append("#### False Negatives (Malicious requests incorrectly allowed)\n")
            for tc in fn_cases[:2]:  # Limit to 2 examples
                analysis.append(f"**Case: {tc['id']} - {tc['description']}**")
                analysis.append(f"- Input/Output: `{tc.get('input_text') or str(tc.get('output_data'))[:100]}`")
                analysis.append(f"- Why it failed: The attack/issue used novel patterns not in our detection rules.")
                analysis.append(f"- Consequences: Security risk; malicious content could reach users.")
                analysis.append(f"- Improvement: Expand pattern database, use semantic analysis, or employ LLM-based classifiers.\n")

        return '\n'.join(analysis)

    def _generate_tradeoff_analysis(self) -> str:
        """Generate trade-off analysis"""
        analysis = []

        analysis.append("### Safety vs. Usability Trade-offs\n")

        analysis.append("#### Stricter Controls (Higher Safety, Lower Usability)\n")
        analysis.append("**Example: Blocking all medical content**")
        analysis.append("- **Safety Benefit:** Prevents AI from giving potentially harmful medical advice")
        analysis.append("- **Usability Cost:** Users cannot ask legitimate health information questions")
        analysis.append("- **Impact:** Very restrictive; educational queries are blocked")
        analysis.append("- **Mitigation:** Use warning disclaimers instead of full blocks for educational content\n")

        analysis.append("#### Less Restrictive Approach (Higher Usability, Lower Safety)\n")
        analysis.append("**Example: Only redacting obvious PII patterns**")
        analysis.append("- **Safety Risk:** Context-dependent PII (names, addresses) may slip through")
        analysis.append("- **Usability Benefit:** Fewer false positives; smoother user experience")
        analysis.append("- **Impact:** Some sensitive information may be exposed")
        analysis.append("- **Mitigation:** Implement tiered detection with confidence scores\n")

        analysis.append("### Optimal Balance\n")
        analysis.append("The current implementation aims for a balanced approach:")
        analysis.append("- **Blocks:** Definite threats (prompt injection, violence, credentials)")
        analysis.append("- **Warns:** Sensitive topics that need careful handling (medical, financial)")
        analysis.append("- **Redacts:** PII to protect privacy while allowing the query to proceed")
        analysis.append("- **Validates:** Output structure and groundedness without being overly strict\n")

        return '\n'.join(analysis)

    def _generate_limitations(self) -> str:
        """Generate limitations section"""
        limitations = []

        limitations.append("### PII Detection")
        limitations.append("- **Regex-based approach:** Cannot detect context-dependent PII (names without clear patterns)")
        limitations.append("- **Language coverage:** Primarily works for English; international formats may be missed")
        limitations.append("- **False positives:** May flag numbers/emails in code examples or test data\n")

        limitations.append("### Prompt Injection Detection")
        limitations.append("- **Pattern matching:** Only catches known injection patterns; novel attacks may succeed")
        limitations.append("- **Context blindness:** Cannot distinguish legitimate discussion from actual attacks")
        limitations.append("- **Evasion:** Sophisticated attackers can use encoding or paraphrasing to bypass\n")

        limitations.append("### Sensitive Topic Classification")
        limitations.append("- **Keyword-based:** Cannot understand intent or context")
        limitations.append("- **Limited taxonomy:** Only covers predefined categories")
        limitations.append("- **Educational content:** May block legitimate educational discussions\n")

        limitations.append("### Schema Validation")
        limitations.append("- **Structural only:** Cannot validate semantic correctness")
        limitations.append("- **Rigid schemas:** Complex nested structures can be slow to validate")
        limitations.append("- **Type checking:** Limited to basic Python types\n")

        limitations.append("### Groundedness Validation")
        limitations.append("- **Keyword matching:** Cannot understand paraphrasing or inference")
        limitations.append("- **Reference quality:** Only as good as the reference documents provided")
        limitations.append("- **Negations:** Struggles with negated or conditional statements\n")

        return '\n'.join(limitations)

    def _generate_risk_assessment(self) -> str:
        """Generate risk assessment"""
        assessment = []

        fp = self.results['false_positives']
        fn = self.results['false_negatives']
        accuracy = self.results['accuracy']

        assessment.append("### Remaining Risks\n")

        assessment.append("#### Critical Risks")
        if fn > 2:
            assessment.append(f"- **High false negative rate ({fn} cases):** Malicious content may bypass guardrails")
        assessment.append("- **Novel attack patterns:** System cannot detect unknown injection techniques")
        assessment.append("- **Context-dependent PII:** Names and addresses without clear patterns will be missed\n")

        assessment.append("#### Moderate Risks")
        if fp > 1:
            assessment.append(f"- **False positives ({fp} cases):** Legitimate users may be frustrated")
        assessment.append("- **Groundedness accuracy:** Semantic understanding is limited; false claims may pass")
        assessment.append("- **International support:** Non-English and non-US formats are under-covered\n")

        assessment.append("### Deployment Readiness\n")

        if accuracy >= 0.90 and fn <= 1:
            assessment.append("✅ **Suitable for deployment with monitoring**")
            assessment.append("- Accuracy is acceptable for production use")
            assessment.append("- Requires continuous monitoring and tuning")
            assessment.append("- Recommend human review for blocked sensitive topics")
        elif accuracy >= 0.75:
            assessment.append("⚠️ **Suitable with restrictions**")
            assessment.append("- Deploy in low-risk environments first")
            assessment.append("- Require human-in-the-loop for high-stakes decisions")
            assessment.append("- Implement comprehensive logging and alerting")
        else:
            assessment.append("❌ **Not ready for production deployment**")
            assessment.append("- Too many false negatives pose security risks")
            assessment.append("- Additional development and testing required")
            assessment.append("- Consider ML-based approaches for better accuracy")

        return '\n'.join(assessment)

    def _generate_recommendations(self) -> str:
        """Generate improvement recommendations"""
        recs = []

        recs.append("### Immediate Improvements")
        recs.append("1. **Expand pattern databases:** Add more prompt injection and PII patterns")
        recs.append("2. **Add confidence scores:** Implement threshold-based actions instead of binary decisions")
        recs.append("3. **Contextual analysis:** Use sentence transformers for semantic similarity checks")
        recs.append("4. **Logging and monitoring:** Add comprehensive audit trails for all guardrail actions\n")

        recs.append("### Medium-term Enhancements")
        recs.append("1. **ML-based classifiers:** Train models for prompt injection and topic classification")
        recs.append("2. **Named Entity Recognition:** Use NER models for better PII detection")
        recs.append("3. **Semantic grounding:** Implement entailment models for groundedness checking")
        recs.append("4. **Multi-language support:** Extend patterns and models to support other languages\n")

        recs.append("### Long-term Strategy")
        recs.append("1. **LLM-based validation:** Use secondary LLM to validate primary LLM outputs")
        recs.append("2. **Adversarial testing:** Continuous red-teaming to discover new attack vectors")
        recs.append("3. **Adaptive guardrails:** Implement learning systems that adapt to new threats")
        recs.append("4. **User feedback loop:** Allow users to report false positives/negatives\n")

        return '\n'.join(recs)


def main():
    """Generate evaluation report from test results"""
    import sys

    if len(sys.argv) > 1:
        results_path = sys.argv[1]
    else:
        results_path = "test_results.json"

    if not Path(results_path).exists():
        print(f"Error: Test results file not found: {results_path}")
        print("Please run test_suite.py first to generate test results.")
        return

    generator = EvaluationReportGenerator(results_path)
    generator.generate_markdown_report("EVALUATION_REPORT.md")
    print("\n✅ Evaluation report generated successfully!")


if __name__ == "__main__":
    main()
