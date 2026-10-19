
╔═══════════════════════════════════════════════════════════════════════════╗
║                    GUARDRAIL SYSTEM ARCHITECTURE                          ║
╚═══════════════════════════════════════════════════════════════════════════╝

                              ┌─────────────┐
                              │  User Input │
                              └──────┬──────┘
                                     │
                                     ▼
        ╔════════════════════════════════════════════════════════╗
        ║           INPUT GUARDRAILS PIPELINE                    ║
        ╠════════════════════════════════════════════════════════╣
        ║                                                        ║
        ║  ┌──────────────────────────────────────────────┐    ║
        ║  │  1. PII Detector                             │    ║
        ║  │     - Regex pattern matching                 │    ║
        ║  │     - Email, phone, SSN, credit card, etc.   │    ║
        ║  │     → Action: REDACT (replace with [REDACTED])│   ║
        ║  └──────────────────────────────────────────────┘    ║
        ║                      │                                ║
        ║                      ▼                                ║
        ║  ┌──────────────────────────────────────────────┐    ║
        ║  │  2. Prompt Injection Detector                │    ║
        ║  │     - Pattern-based detection                │    ║
        ║  │     - Instruction override attempts          │    ║
        ║  │     - Role manipulation, constraint bypass   │    ║
        ║  │     → Action: BLOCK (stop processing)        │    ║
        ║  └──────────────────────────────────────────────┘    ║
        ║                      │                                ║
        ║                      ▼                                ║
        ║  ┌──────────────────────────────────────────────┐    ║
        ║  │  3. Sensitive Topic Classifier               │    ║
        ║  │     - Keyword-based classification           │    ║
        ║  │     - Medical, financial, legal, violence    │    ║
        ║  │     → Action: BLOCK/WARN based on severity   │    ║
        ║  └──────────────────────────────────────────────┘    ║
        ║                                                        ║
        ╚════════════════════════════════════════════════════════╝
                                     │
                        ┌────────────┴────────────┐
                        │                         │
                     BLOCKED                   ALLOWED
                        │                         │
                        ▼                         ▼
                ┌───────────────┐      ┌─────────────────────┐
                │  Error Message│      │  Processed Input    │
                │  to User      │      │  (PII redacted)     │
                └───────────────┘      └──────────┬──────────┘
                                                  │
                                                  ▼
                                     ┌──────────────────────┐
                                     │   AI MODEL           │
                                     │   (LLM Processing)   │
                                     │                      │
                                     │  Generate Response   │
                                     └──────────┬───────────┘
                                                │
                                                ▼
        ╔════════════════════════════════════════════════════════╗
        ║           OUTPUT GUARDRAILS PIPELINE                   ║
        ╠════════════════════════════════════════════════════════╣
        ║                                                        ║
        ║  ┌──────────────────────────────────────────────┐    ║
        ║  │  1. Schema Validator                         │    ║
        ║  │     - Type checking                          │    ║
        ║  │     - Required fields validation             │    ║
        ║  │     - Value range validation                 │    ║
        ║  │     → Action: FALLBACK if invalid            │    ║
        ║  └──────────────────────────────────────────────┘    ║
        ║                      │                                ║
        ║                      ▼                                ║
        ║  ┌──────────────────────────────────────────────┐    ║
        ║  │  2. Groundedness Validator                   │    ║
        ║  │     - Extract claims from response           │    ║
        ║  │     - Check against reference documents      │    ║
        ║  │     - Keyword/phrase matching                │    ║
        ║  │     → Action: WARN if unsupported claims     │    ║
        ║  └──────────────────────────────────────────────┘    ║
        ║                      │                                ║
        ║                      ▼                                ║
        ║  ┌──────────────────────────────────────────────┐    ║
        ║  │  3. Sensitive Information Detector           │    ║
        ║  │     - Check for PII in output                │    ║
        ║  │     - Check for credentials/secrets          │    ║
        ║  │     - API keys, passwords, tokens            │    ║
        ║  │     → Action: REDACT or BLOCK                │    ║
        ║  └──────────────────────────────────────────────┘    ║
        ║                                                        ║
        ╚════════════════════════════════════════════════════════╝
                                     │
                        ┌────────────┴────────────┐
                        │                         │
                   INVALID/BLOCKED             VALID
                        │                         │
                        ▼                         ▼
                ┌───────────────┐      ┌─────────────────────┐
                │  Fallback     │      │  Processed Output   │
                │  Response or  │      │  (Redacted if       │
                │  Regenerate   │      │   necessary)        │
                └───────────────┘      └──────────┬──────────┘
                                                  │
                                                  ▼
                                     ┌──────────────────────┐
                                     │   AUDIT LOG          │
                                     │   - Timestamp        │
                                     │   - Actions taken    │
                                     │   - Flags raised     │
                                     │   - Metadata         │
                                     └──────────┬───────────┘
                                                │
                                                ▼
                                        ┌───────────────┐
                                        │  User Receives│
                                        │  Safe Response│
                                        └───────────────┘


═══════════════════════════════════════════════════════════════════════════

KEY COMPONENTS:

┌─────────────────────────────────────────────────────────────────────────┐
│  GuardrailPipeline                                                      │
│  - Orchestrates input and output guardrails                             │
│  - Maintains audit log of all checks                                    │
│  - Returns pass/fail status with detailed metadata                      │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  Actions:                                                               │
│  - ALLOW: Pass through without modification                             │
│  - REDACT: Remove sensitive information, then pass                      │
│  - BLOCK: Stop processing entirely                                      │
│  - WARN: Flag for attention but allow to proceed                        │
│  - REGENERATE: Request new output generation                            │
│  - FALLBACK: Return safe default response                               │
└─────────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════

INTERACTION FLOW:

1. User submits input → Input Guardrails filter/validate
2. If blocked: return error message immediately
3. If allowed: process input (with PII redacted) → AI Model
4. AI generates response → Output Guardrails validate
5. If invalid: return fallback or regenerate
6. If valid: return processed output (with any redactions)
7. Log all actions and flags for audit trail

═══════════════════════════════════════════════════════════════════════════
