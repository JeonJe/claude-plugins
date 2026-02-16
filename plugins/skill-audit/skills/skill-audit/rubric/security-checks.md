# Security and Sharing Checks

Perform these checks for publish readiness:
- MUST flag hardcoded secrets (API keys, tokens, passwords, private keys).
- MUST flag personal or machine-specific paths unless intentionally documented.
- MUST flag internal-only names/assumptions without fallback guidance.
- MUST include a privacy note when scanning user-home content.

## Recommended Secret Patterns
- `sk-`, `ghp_`, `github_pat_`, `xoxb-`, `xoxp-`
- `BEGIN ... PRIVATE KEY`
- `api_key`, `token`, `password`, `secret`

## Anti-Patterns (Deductions)

| Pattern | Deduction | Why |
|---|---:|---|
| Description too vague to route reliably | -10 | Reduces trigger quality |
| Bloated top-level file with weak structure | -10 | Hurts context efficiency |
| No validation loop | -5 | Increases skipped verification risk |
| Deep, hard-to-follow reference chains | -5 | Reduces execution reliability |
| Missing security/share checks | -10 | Unsafe for public sharing |
| Hardcoded secrets or sensitive values | -20 | Immediate publish blocker |
