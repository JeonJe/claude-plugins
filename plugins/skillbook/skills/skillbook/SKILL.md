---
name: skillbook
description: "Pokemon Pokedex-style skill dashboard. Tracks usage, levels, rarity, achievements. Use when: 'show skills', 'skill stats', 'open dashboard'. Not for skill auditing."
model: haiku
---

# Skillbook - Pokemon Pokedex-style Skill Dashboard

## Use Cases

**1. Open Dashboard** (default)
- Input: "skillbook", "skill stats", "open dashboard"
- Action: Generate and open web dashboard in browser
- Output: Pokemon card UI + charts + achievement badges

**2. Query Specific Skill**
- Input: "gg skill stats"
- Action: Highlight skill in dashboard
- Output: Skill card + usage history

**3. Category Overview**
- Input: "study skills overview"
- Action: Filter by category
- Output: Filtered skill list + progress

**4. Terminal Mode**
- Input: "skillbook terminal stats"
- Action: Text-based output in CLI
- Output: Compact skill list with levels and rarity

## Don't use when

- Skill quality audit -> use **skill-audit** instead
- Editing skill definitions -> edit SKILL.md directly

## Execution

```bash
python3 <SKILL_DIR>/skillbook.py dashboard
```

Runs immediately on skill invocation, outputs directly.

## Data

Stats file: `~/.claude/skillbook-stats.json` (default)

Custom location: create `~/.claude/skillbook.config.json`:
```json
{
  "statsFile": "~/your/path/skill-stats.json"
}
```
