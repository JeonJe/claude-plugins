# Skill Audit

Audit Claude Code skills and commands for publish readiness. Scores against Anthropic's [skill best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) and returns concrete fixes.

```
/skill-audit my-skill
       |
       v
  6-category rubric scoring
       |
       v
  Security & sharing checks
       |
       v
  Grade (A-D) + prioritized fixes
```

## Why

Sharing a skill without checking quality leads to vague triggers, bloated bodies, missing validation loops, and leaked secrets. Skill Audit applies a deterministic 100-point rubric so you know exactly what to fix before publishing.

## Features

### 6-Category Rubric (100 points)

| Category | Points | What it checks |
|----------|-------:|----------------|
| Trigger Quality | 20 | Description clarity, routing precision, collision avoidance |
| Body Boundaries | 20 | Execution focus, no routing noise in body |
| Progressive Disclosure | 15 | Top-level conciseness, reference depth |
| Token Efficiency | 15 | No filler, no duplication |
| Validation Loop | 15 | Verify steps, strong requirement language |
| Composability | 15 | Use cases, integration points |

### Grading

| Grade | Score | Meaning |
|-------|------:|---------|
| A | 90-100 | Ready to share |
| B | 80-89 | Share after minor fixes |
| C | 70-79 | Needs targeted rewrite |
| D | <70 | Redesign before sharing |

### Security Checks

Anti-patterns that trigger automatic deductions:

- Hardcoded secrets (`sk-`, `ghp_`, API keys) — **-20**
- Vague description — **-10**
- Bloated top-level file — **-10**
- Missing security checks — **-10**
- No validation loop — **-5**
- Deep reference chains — **-5**

### Fix Loop

Request fixes and the skill will apply them, re-audit, and verify the score improved.

## Quick Start

```bash
# Via marketplace
/plugin marketplace add JeonJe/claude-plugins
/plugin install skill-audit

# Or manually
git clone https://github.com/JeonJe/claude-plugins.git
cp -r claude-plugins/plugins/skill-audit/skills/skill-audit ~/.claude/skills/
```

## Usage

| Command | Description |
|---------|-------------|
| `/skill-audit` | Audit all project skills/commands |
| `/skill-audit my-skill` | Deep audit single target |
| `/skill-audit --include-user-home` | Include `~/.claude/` paths |

## Requirements

- Claude Code CLI
- No external dependencies (uses built-in Glob, Grep, Read tools only)

## File Structure

```
skill-audit/
├── skills/skill-audit/
│   ├── SKILL.md               # Skill definition + workflow
│   ├── rubric/
│   │   ├── scoring.md         # 6-category rubric
│   │   └── security-checks.md # Anti-patterns + deductions
│   └── templates/
│       └── output-format.md   # Report template
├── .claude-plugin/plugin.json
├── LICENSE
└── README.md
```

## License

MIT
