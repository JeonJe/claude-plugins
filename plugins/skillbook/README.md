# Skillbook

Pokemon Pokedex-style skill dashboard for Claude Code. Every skill you use becomes a collectible card with levels, rarity, and achievements.

## Quick Start

```bash
/skillbook install     # Auto-setup everything
/skillbook             # Open dashboard
```

That's it. No manual configuration needed. The installer handles copying files, merging hooks, and creating config.

## What It Does

```
1. You use any /skill (e.g., /commit, /study, /interview)
2. Hook auto-tracks usage count in skill-stats.json
3. /skillbook opens a web dashboard showing your collection
4. Skills level up and earn rarity stars as you use them more
```

## Usage

| Command | Description |
|---------|-------------|
| `/skillbook` | Open web dashboard in browser (default) |
| `/skillbook stats` | Show summary in terminal |
| `/skillbook used` | Show only discovered (used) skills |
| `/skillbook pinned` | Show pinned/favorite skills |
| `/skillbook pin <name>` | Toggle favorite on a skill |
| `/skillbook <category>` | Filter by category (e.g., `study`, `git`, `code`) |
| `/skillbook install` | Auto-setup: copy files, merge hooks, create config |
| `/skillbook uninstall` | Remove hooks (keeps skill files) |
| `/skillbook uninstall --purge` | Remove hooks + skill files (keeps stats) |
| `/skillbook status` | Show installation health |

## Screenshots

### Dashboard Overview

See your entire skill journey at a glance: total discovered skills, cumulative level, achievement badges, personalized recommendations, workflow sequences, category progress bars, and a 7-day usage trend chart. Know exactly where you stand and what to explore next.

![Dashboard Overview](../../assets/dashboard-full.png)

### Skill Cards

Every skill you use becomes a collectible card with its own Pokemon sprite (determined by skill name), level, rarity stars, category badge, and usage count. Pinned favorites appear first. Instantly see which skills you rely on most and which categories you're building expertise in.

![Skill Cards](../../assets/skill-cards.png)

### Undiscovered Skills

Skills you haven't tried yet appear as dark silhouettes at the bottom of your collection, encouraging you to experiment with new workflows. The contrast between colorful discovered cards and shadowed unknowns creates a natural motivation to "catch 'em all."

![Undiscovered Cards](../../assets/skill-cards-bottom.png)

### Skill Detail Modal

Click any card to open a detailed view with total uses, current level, and last-used date. A one-click copy button lets you paste the skill command directly into Claude Code.

![Detail Modal](../../assets/skill-detail-modal.png)

## Features

### Skill Cards
Each skill gets a unique Pokemon sprite (deterministic hash). Cards show level, rarity stars, category, and usage count.

### Leveling System
```
Level = floor(sqrt(uses * 10))

Example:
  1 use  → Lv.3
  5 uses → Lv.7
  10 uses → Lv.10
  50 uses → Lv.22
  100 uses → Lv.31
```

### Rarity Tiers

| Stars | Tier | Uses Required |
|-------|------|---------------|
| ★★★★★ | Legendary | 100+ |
| ★★★★☆ | Epic | 50-99 |
| ★★★☆☆ | Rare | 20-49 |
| ★★☆☆☆ | Uncommon | 5-19 |
| ★☆☆☆☆ | Common | 1-4 |
| ? | Undiscovered | 0 |

### Achievements
Unlock badges as you reach milestones:

| Badge | Name | Condition |
|-------|------|-----------|
| 🩸 | First Blood | Use your first skill |
| 🧭 | Explorer | Discover 10+ skills |
| 🔥 | Dedicated | Use any skill 10+ times |
| 👑 | Expert | Use any skill 50+ times |
| 🌍 | Polyglot | Use skills from 5+ categories |
| 🚗 | Daily Driver | 100+ total uses |

### Categories
Skills are auto-categorized by keyword matching:

| Category | Keywords | How It Works |
|----------|----------|--------------|
| 📁 Git | commit, pr, branch, worktree, git | If skill name contains "commit" → Git category |
| 💻 Code | code, review, refactor, fix | If skill name contains "review" → Code category |
| 🧪 Test | test, e2e, coverage | If skill name contains "test" → Test category |
| 📝 Docs | doc, update-docs, codemaps | If skill name contains "doc" → Docs category |
| 📋 Plan | plan, issue, clarify | If skill name contains "plan" → Plan category |
| 📚 Study | study, gg, interview, learn | If skill name contains "study" → Study category |
| 📄 Resume | resume | If skill name contains "resume" → Resume category |
| 🧩 Algo | algo | If skill name contains "algo" → Algo category |
| 🎯 PM | jira, jd, ticket, agile | If skill name contains "jira" → PM category |
| 🔌 Plugin | sisyphus, council, calendar | Plugin-related skills |
| ✨ Misc | (no match) | Fallback for unmatched skills |

**Example:** Your skill `/my-code-review` automatically goes to 💻 Code category because it contains "review".

### Web Dashboard
Interactive HTML dashboard with:
- Skill cards with Pokemon sprites
- Search and filter (All / Discovered / Pinned / Local / Commands)
- Sort by uses, level, recent, or name
- Category progress bars
- 7-day usage trend chart
- Achievement badges
- Workflow recommendations
- Click any card for detailed skill info

## Configuration (Optional)

**Zero config required.** Stats auto-save to `~/.claude/skillbook-stats.json`.

To customize (e.g., move stats to Obsidian vault), create `~/.claude/skillbook.config.json`:

```json
{
  "statsFile": "~/path/to/your/skill-stats.json",
  "outputDir": "~/path/to/dashboard/output",
  "language": "en"
}
```

| Key | Default | Description |
|-----|---------|-------------|
| `statsFile` | `~/.claude/skillbook-stats.json` | Where usage data is stored |
| `outputDir` | `~/.claude/skillbook/` | Where dashboard HTML is generated |
| `language` | `en` | Dashboard language (`en` or `ko`) |

## Manual Installation

<details>
<summary>Click to expand manual steps (not recommended - use /skillbook install instead)</summary>

### Step 1: Install Plugin

```bash
# Via marketplace
/plugin marketplace add JeonJe/claude-plugins
/plugin install skillbook

# Or manually
git clone https://github.com/JeonJe/claude-plugins.git
cp -r claude-plugins/plugins/skillbook/skills/skillbook ~/.claude/skills/
```

### Step 2: Enable Auto-Tracking (Required)

Add the usage tracking hook to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/skill-usage-tracker.py"
          }
        ]
      }
    ]
  }
}
```

> **Note**: If you already have `UserPromptSubmit` hooks, add the new hook entry to the existing array.

Copy the hook file:

```bash
cp claude-plugins/plugins/skillbook/hooks/skill-usage-tracker.py ~/.claude/hooks/
chmod +x ~/.claude/hooks/skill-usage-tracker.py
```

### Step 3: Verify

```bash
# Use any skill, then check if it was tracked:
/skillbook stats
```

You should see `Total Uses: 1x` after using your first skill.

</details>

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `/skillbook install` fails | Run `/skillbook status` to see what's missing. Check Python version: `python3 --version` should be 3.8+ |
| Hook not tracking skills | Verify `~/.claude/settings.json` has a `UserPromptSubmit` entry with the hook command. Run `/skillbook status` to verify. |
| Dashboard won't open | Make sure Python 3.8+ is installed: `python3 --version`. Try `/skillbook terminal stats` to check if tracking works. |
| Stats not updating | Check that hook is executable: `ls -l ~/.claude/hooks/skill-usage-tracker.py` should show `x`. Verify config path in `~/.claude/skillbook.config.json`. |
| "Permission denied" on hook | Fix executable permission: `chmod +x ~/.claude/hooks/skill-usage-tracker.py` |
| Existing hook conflict | If you have an old hook installed, uninstall first: `/skillbook uninstall`, then `/skillbook install` |

## Uninstall

Remove skillbook from your system:

```bash
/skillbook uninstall           # Remove hooks only (keeps stats and skill files)
/skillbook uninstall --purge   # Remove hooks + skill files (keeps stats as backup)
```

**Note**: Stats file is never deleted. Your data is safe.

## File Structure

```
skillbook/
├── hooks/
│   └── skill-usage-tracker.py   # Auto-counts /skill usage (UserPromptSubmit hook)
├── skills/skillbook/
│   ├── SKILL.md                  # Skill definition for Claude
│   ├── skillbook.py              # CLI interface
│   ├── skillbook_dashboard.py    # Web dashboard generator
│   ├── installer.py              # Auto-installer
│   ├── config/                   # Category, level, rarity docs
│   └── templates/                # Card format templates
├── .claude-plugin/plugin.json
└── README.md
```

## Requirements

- Python 3.8+
- Browser (for dashboard)
- No other dependencies (no `jq`, no npm packages)

## License

MIT
