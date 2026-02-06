# claude-plugins

A collection of Claude Code plugins for developer productivity, learning, and career growth.

## Quick Start

```bash
# 1. Add marketplace
/plugin marketplace add JeonJe/claude-plugins

# 2. Install a plugin
/plugin install skillbook
```

## Available Plugins

| Plugin | Description | Key Features |
|--------|-------------|--------------|
| [skillbook](./plugins/skillbook) | Pokemon Pokedex-style skill dashboard | Auto usage tracking, leveling, achievements, web dashboard |

## Preview

![Skillbook Dashboard](./assets/dashboard-full.png)

## How It Works

```
You type /skill-name
       |
       v
[Hook] skill-usage-tracker.sh  -->  Updates skill-stats.json (usage +1)
       |
       v
[Skill] /skillbook              -->  Reads skill-stats.json
       |
       v
[Output] Web dashboard or CLI stats with levels, rarity, achievements
```

Each plugin may include:
- **skills/**: Skill definitions (SKILL.md + scripts)
- **hooks/**: Auto-triggers that run on events (e.g., usage tracking)

## Plugin Structure

```
plugins/<plugin-name>/
├── .claude-plugin/
│   └── plugin.json        # Plugin metadata
├── hooks/                  # Event-driven scripts (optional)
├── skills/
│   └── <skill-name>/
│       └── SKILL.md        # Skill definition
└── README.md
```

## Contributing

PRs welcome! See each plugin's README for details.

## License

MIT
