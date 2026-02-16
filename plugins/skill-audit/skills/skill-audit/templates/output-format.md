# Output Format

```markdown
## Skill Audit Report

### Scope
- Target: <name or all>
- Paths scanned: <paths>
- Include user-home: <yes/no>
- Parsed flags: <flags>

### Summary
| Item | Score | Grade | Blockers | Key Issues |
|---|---:|---|---|---|
| my-skill | 84/100 | B | No | Trigger overlap with X |

### Findings: <item>
1. Trigger Quality: 16/20
- [x] Clear user phrasing in description
- [ ] Overlaps with <other-item> on "audit" keyword without disambiguator (-4)

2. Body Responsibility Boundaries: 17/20
- [x] Actionable workflow exists
- [ ] Some routing notes should be tightened (-3)

3. Progressive Disclosure: 14/15
4. Token Efficiency: 11/15
5. Validation Loop: 13/15
6. Composability and Reuse: 13/15

Security and Sharing:
- [x] No secrets detected
- [x] No machine-specific paths in examples
- [ ] Internal-only dependency name without fallback (-5)

Anti-pattern deductions: -5
Final score: 84/100 (B)

### Recommended Fixes (Priority Order)
1. Remove trigger overlap by narrowing description terms.
2. Add fallback path for internal dependency.
3. Replace long prose with checklist bullets in section X.
```
