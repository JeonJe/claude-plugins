# Audit Rubric (100 points)

## 1. Trigger Quality (20)
Best-practice alignment: `description` should be concrete and act as the routing trigger.

| Check | Points | Criteria |
|---|---:|---|
| [ ] | 8 | Description includes realistic user phrasing ("audit", "skill quality check", "publish readiness") |
| [ ] | 5 | Clear negative routing guidance when needed |
| [ ] | 4 | No obvious keyword collision with nearby skills/commands |
| [ ] | 3 | Clear, concise, and third-person style |

## 2. Body Responsibility Boundaries (20)
Body should focus on execution guidance, not vague routing noise.

| Check | Points | Criteria |
|---|---:|---|
| [ ] | 10 | Body is task/procedure focused and not bloated with trigger chatter |
| [ ] | 5 | Constraints and exceptions are explicit and actionable |
| [ ] | 5 | Steps explain what to do and how to verify outcomes |

## 3. Progressive Disclosure (15)
Keep top-level short; move depth into references.

| Check | Points | Criteria |
|---|---:|---|
| [ ] | 5 | Top-level file stays concise (target: <= 500 lines) |
| [ ] | 5 | Detailed guidance is split into focused referenced files |
| [ ] | 3 | References are shallow and easy to follow |
| [ ] | 2 | Large referenced docs include quick navigation cues |

## 4. Token Efficiency (15)
Avoid repeating what the model already knows.

| Check | Points | Criteria |
|---|---:|---|
| [ ] | 5 | Minimal generic theory text |
| [ ] | 4 | Minimal roleplay/persona filler |
| [ ] | 3 | Prefer concrete examples/checklists over long prose |
| [ ] | 3 | No major duplication across sections |

## 5. Validation Loop (15)
Include explicit execute -> verify -> fix -> re-verify flow.

| Check | Points | Criteria |
|---|---:|---|
| [ ] | 6 | Workflow includes explicit verification checkpoints |
| [ ] | 4 | Uses strong requirement language (`MUST`, `NEVER`) where critical |
| [ ] | 3 | Stepwise checklist exists |
| [ ] | 2 | Failure handling is specific |

## 6. Composability and Reuse (15)
Show how this command works with others.

| Check | Points | Criteria |
|---|---:|---|
| [ ] | 6 | 2-3 concrete use cases (Input -> Action -> Output) |
| [ ] | 5 | Explicit integration points with related tools/commands |
| [ ] | 4 | Conflicting or overlapping tools are clarified |

## Scoring Consistency Rules
Use these deterministic rules to reduce reviewer variance:
- Trigger collision check: mark collision only when 2+ sibling items share the same primary intent keyword and no disambiguator exists.
- Progressive disclosure check: fail only when top-level exceeds 500 lines or references require 2+ nested hops for core flow.
- Token efficiency check: deduct only for repeated paragraphs (>1 near-duplicate block) or generic filler without execution value.
- Validation loop check: fail only if no explicit verify step is present after execution.
- Final score MUST be clamped to `0..100`.
