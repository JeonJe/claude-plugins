#!/bin/bash
# Auto-track skill usage for Skillbook
# Hook type: UserPromptSubmit
# When a user types /skill-name, this hook increments the usage counter.
#
# Setup: Add to ~/.claude/settings.json under hooks.UserPromptSubmit:
#   {
#     "hooks": [{
#       "type": "command",
#       "command": "bash <PLUGIN_PATH>/hooks/skill-usage-tracker.sh"
#     }]
#   }

INPUT_JSON=$(cat)
PROMPT=$(echo "$INPUT_JSON" | jq -r '.prompt // empty' 2>/dev/null)

[ -z "$PROMPT" ] && exit 0

# Extract /command from prompt
COMMAND=$(echo "$PROMPT" | grep -oE '^/[a-zA-Z0-9_:-]+' | head -1 | sed 's/^\///')

[ -z "$COMMAND" ] && exit 0

# Paths
COMMANDS_DIR="$HOME/.claude/commands"
SKILLS_DIR="$HOME/.claude/skills"
PLUGINS_DIR="$HOME/.claude/plugins"
INSTALLED_PLUGINS="$PLUGINS_DIR/installed_plugins.json"

# Check if the command matches a known skill
check_skill_exists() {
    local name="$1"

    # 1. commands/*.md
    [ -f "$COMMANDS_DIR/$name.md" ] && return 0

    # 2. skills/*/SKILL.md
    [ -f "$SKILLS_DIR/$name/SKILL.md" ] && return 0

    # 3. Plugin skills (plugin:skill or plugin format)
    if [ -f "$INSTALLED_PLUGINS" ]; then
        local plugin_name="${name%%:*}"
        local skill_name="${name#*:}"

        [ "$plugin_name" = "$skill_name" ] && skill_name=""

        local plugin_paths=$(jq -r ".plugins | to_entries[] | select(.key | startswith(\"$plugin_name@\")) | .value[].installPath" "$INSTALLED_PLUGINS" 2>/dev/null)

        for path in $plugin_paths; do
            [ -f "$path/SKILL.md" ] && return 0
            if [ -n "$skill_name" ]; then
                [ -f "$path/skills/$skill_name/SKILL.md" ] && return 0
            fi
            [ -f "$path/skills/$plugin_name/SKILL.md" ] && return 0
        done
    fi

    return 1
}

check_skill_exists "$COMMAND" || exit 0

# Update stats using Python (reads config for stats file location)
python3 - "$COMMAND" << 'PYEOF'
import json
import math
import sys
from datetime import datetime
from pathlib import Path

name = sys.argv[1] if len(sys.argv) > 1 else None
if not name:
    sys.exit(0)

# Load config for stats file location
HOME = Path.home()
CONFIG_FILE = HOME / ".claude" / "skillbook.config.json"
STATS_FILE = HOME / ".claude" / "skillbook-stats.json"

if CONFIG_FILE.exists():
    try:
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
        if "statsFile" in cfg:
            STATS_FILE = Path(cfg["statsFile"]).expanduser().resolve()
    except (OSError, json.JSONDecodeError):
        pass

# Load or create stats
if STATS_FILE.exists():
    with open(STATS_FILE) as f:
        stats = json.load(f)
else:
    stats = {"version": 1, "totalUses": 0, "skills": {}}

if name not in stats["skills"]:
    stats["skills"][name] = {"uses": 0, "lastUsed": None, "pinned": False}

old_level = max(1, int(math.sqrt(stats["skills"][name]["uses"] * 10))) if stats["skills"][name]["uses"] > 0 else 0

stats["skills"][name]["uses"] += 1
stats["skills"][name]["lastUsed"] = datetime.now().strftime("%Y-%m-%d")
stats["totalUses"] = stats.get("totalUses", 0) + 1
stats["lastUpdated"] = datetime.now().strftime("%Y-%m-%d")

new_level = max(1, int(math.sqrt(stats["skills"][name]["uses"] * 10)))

STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
with open(STATS_FILE, "w") as f:
    json.dump(stats, f, indent=2, ensure_ascii=False)

if new_level > old_level:
    print(f"\U0001f389 /{name} Level Up! Lv.{old_level} \u2192 Lv.{new_level}")
PYEOF
