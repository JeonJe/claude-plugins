#!/usr/bin/env python3
"""
Skill Usage Tracker for Skillbook
Hook type: UserPromptSubmit

Tracks /command and /skill usage, incrementing counters in a stats file.
Supports alias mapping, plugin skill detection, and level-up notifications.

Setup: Add to ~/.claude/settings.json under hooks.UserPromptSubmit:
  {
    "hooks": [{
      "type": "command",
      "command": "python3 ~/.claude/hooks/skill-usage-tracker.py"
    }]
  }

Requires: Python 3.8+ (no external dependencies)
"""

import json
import math
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Alias mapping: short command -> canonical skill name
# Add entries here to map shorthand commands to their full skill identifiers.
# ---------------------------------------------------------------------------
ALIASES = {
    "wrap": "session-wrap:wrap",
}


def read_stdin_json():
    """Read and parse JSON from stdin (hook input)."""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return None
        return json.loads(raw)
    except (json.JSONDecodeError, OSError):
        return None


def extract_command(prompt):
    """Extract /command from the beginning of the prompt string."""
    if not prompt:
        return None
    match = re.match(r'^/([a-zA-Z0-9_:-]+)', prompt)
    if not match:
        return None
    return match.group(1)


def resolve_alias(command):
    """Resolve alias to canonical skill name if one exists."""
    return ALIASES.get(command, command)


def get_stats_path():
    """
    Determine the stats file path.
    Priority: config file -> default location.
    """
    home = Path.home()
    config_path = home / ".claude" / "skillbook.config.json"
    default_path = home / ".claude" / "skillbook-stats.json"

    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                cfg = json.load(f)
            raw = cfg.get("statsFile", "")
            if raw:
                return Path(os.path.expanduser(raw)).resolve()
        except (OSError, json.JSONDecodeError, TypeError):
            pass

    return default_path


def check_skill_exists(name):
    """
    Check if the given command/skill name corresponds to a known skill.

    Searches in order:
      1. ~/.claude/commands/<name>.md
      2. ~/.claude/skills/<name>/SKILL.md
      3. Installed plugin skills (plugin:skill or plugin format)
    """
    home = Path.home()
    commands_dir = home / ".claude" / "commands"
    skills_dir = home / ".claude" / "skills"
    plugins_dir = home / ".claude" / "plugins"
    installed_plugins_path = plugins_dir / "installed_plugins.json"

    # 1. commands/*.md
    if (commands_dir / (name + ".md")).is_file():
        return True

    # 2. skills/*/SKILL.md
    if (skills_dir / name / "SKILL.md").is_file():
        return True

    # 3. Plugin skills
    if installed_plugins_path.is_file():
        try:
            with open(installed_plugins_path, "r") as f:
                plugins_data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return False

        plugins = plugins_data.get("plugins", {})
        if not isinstance(plugins, dict):
            return False

        # Parse plugin:skill format
        if ":" in name:
            plugin_name = name.split(":")[0]
            skill_name = name.split(":", 1)[1]
        else:
            plugin_name = name
            skill_name = ""

        for key, entries in plugins.items():
            # Match plugin key that starts with plugin_name@
            if not key.startswith(plugin_name + "@"):
                continue
            if not isinstance(entries, list):
                continue
            for entry in entries:
                install_path = entry.get("installPath", "")
                if not install_path:
                    continue
                p = Path(install_path)

                # Root SKILL.md
                if (p / "SKILL.md").is_file():
                    return True

                # skills/{skill_name}/SKILL.md
                if skill_name and (p / "skills" / skill_name / "SKILL.md").is_file():
                    return True

                # skills/{plugin_name}/SKILL.md
                if (p / "skills" / plugin_name / "SKILL.md").is_file():
                    return True

    return False


def load_stats(stats_path):
    """Load existing stats or return a fresh structure."""
    if stats_path.is_file():
        try:
            with open(stats_path, "r") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
    return {"version": 1, "totalUses": 0, "skills": {}}


def calculate_level(uses):
    """Calculate skill level from usage count."""
    if uses <= 0:
        return 0
    return max(1, int(math.sqrt(uses * 10)))


def write_stats_atomic(stats_path, stats):
    """
    Write stats to file atomically.
    Uses a temporary file + rename to prevent data corruption on crash.
    """
    stats_path.parent.mkdir(parents=True, exist_ok=True)

    # Write to a temp file in the same directory, then rename
    fd, tmp_path = tempfile.mkstemp(
        dir=str(stats_path.parent),
        prefix=".skillbook-stats-",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp_path, str(stats_path))
    except OSError:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def update_stats(name, stats_path):
    """
    Increment usage counter for the given skill and write to disk.
    Returns (old_level, new_level) for level-up detection.
    """
    stats = load_stats(stats_path)

    skills = stats.get("skills", {})
    if name not in skills:
        skills[name] = {"uses": 0, "lastUsed": None, "pinned": False}

    old_level = calculate_level(skills[name]["uses"])

    # Create updated skill entry (immutable pattern)
    today = datetime.now().strftime("%Y-%m-%d")
    updated_skill = {
        **skills[name],
        "uses": skills[name]["uses"] + 1,
        "lastUsed": today,
    }
    updated_skills = {**skills, name: updated_skill}

    updated_stats = {
        **stats,
        "skills": updated_skills,
        "totalUses": stats.get("totalUses", 0) + 1,
        "lastUpdated": today,
    }

    new_level = calculate_level(updated_skill["uses"])

    write_stats_atomic(stats_path, updated_stats)

    return old_level, new_level


def main():
    # 1. Read hook input from stdin
    input_data = read_stdin_json()
    if input_data is None:
        return

    prompt = input_data.get("prompt", "")
    if not prompt:
        return

    # 2. Extract /command
    command = extract_command(prompt)
    if not command:
        return

    # 3. Resolve aliases
    command = resolve_alias(command)

    # 4. Check if it is a known skill
    if not check_skill_exists(command):
        return

    # 5. Determine stats file location
    stats_path = get_stats_path()

    # 6. Update stats and check for level-up
    try:
        old_level, new_level = update_stats(command, stats_path)
    except OSError:
        return

    # 7. Level-up notification
    if new_level > old_level:
        print(
            "\U0001f389 /{command} Level Up! Lv.{old} -> Lv.{new}".format(
                command=command, old=old_level, new=new_level,
            )
        )


if __name__ == "__main__":
    main()
