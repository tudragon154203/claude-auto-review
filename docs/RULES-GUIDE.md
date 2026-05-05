# Rules Guide

Rules live in `.claude/claude-auto-review/rules.md` so teams can commit review criteria with the project.

Good rules are specific and reviewable:

```markdown
## Security

- Never use permissive fallback values for authentication, authorization, tenancy, or ownership checks.
- Do not log secrets, credentials, tokens, personal data, or raw authorization headers.
```

Weak rules are too broad:

```markdown
- Make the code good.
- Improve naming.
```

Use severity in the review output, not necessarily in every rule. The reviewer maps violations to:

- CRITICAL: security vulnerability, data loss, unsafe irreversible behavior
- HIGH: type safety hole, dangerous fallback, contract mismatch
- MEDIUM: domain leakage, ambiguous naming that violates a rule, maintainability risk
- LOW: informational issue that does not need to block stop
