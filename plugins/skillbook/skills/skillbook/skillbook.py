#!/usr/bin/env python3
"""
Skillbook - Pokemon Pokedex-style skill tracker for Claude Code
Usage: python skillbook.py [dashboard|terminal|stats|pin <skill>|use <skill>|install|uninstall|status]
"""

import json
import math
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Paths
HOME = Path.home()
CLAUDE_DIR = HOME / ".claude"
SKILLS_DIR = CLAUDE_DIR / "skills"
COMMANDS_DIR = CLAUDE_DIR / "commands"
PLUGINS_DIR = CLAUDE_DIR / "plugins"
INSTALLED_PLUGINS_FILE = PLUGINS_DIR / "installed_plugins.json"
CONFIG_FILE = CLAUDE_DIR / "skillbook.config.json"


def _load_config():
    """Load config from ~/.claude/skillbook.config.json if exists.

    Supported keys:
        statsFile: Path to skill-stats.json (supports ~)
        outputDir: Path to dashboard output directory (supports ~)

    Returns:
        dict with Path values, empty dict if no config or parse error.
    """
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                cfg = json.load(f)
            result = {}
            for k, v in cfg.items():
                if isinstance(v, str):
                    result[k] = Path(v).expanduser().resolve()
            return result
        except json.JSONDecodeError as e:
            print(f"\u26a0\ufe0f  Malformed config at {CONFIG_FILE}: line {e.lineno}", file=sys.stderr)
            print("   Using default settings.", file=sys.stderr)
        except OSError as e:
            print(f"\u26a0\ufe0f  Cannot read config: {e}", file=sys.stderr)
    return {}


_config = _load_config()
STATS_FILE = _config.get("statsFile", CLAUDE_DIR / "skillbook-stats.json")

# Categories - keyword-based auto-classification
CATEGORIES = {
    "git": {"icon": "\U0001f4c1", "name": "Git", "keywords": ["commit", "pr", "branch", "worktree", "git"]},
    "code": {"icon": "\U0001f4bb", "name": "Code", "keywords": ["code", "review", "tdd", "build", "refactor", "restructure", "fix"]},
    "test": {"icon": "\U0001f9ea", "name": "Test", "keywords": ["test", "e2e", "coverage"]},
    "docs": {"icon": "\U0001f4dd", "name": "Docs", "keywords": ["doc", "update-docs", "codemaps"]},
    "plan": {"icon": "\U0001f4cb", "name": "Plan", "keywords": ["plan", "issue", "clarify", "prometheus", "momus"]},
    "study": {"icon": "\U0001f4da", "name": "Study", "keywords": ["study", "gg", "interview", "learn", "wrap"]},
    "resume": {"icon": "\U0001f4c4", "name": "Resume", "keywords": ["resume"]},
    "algo": {"icon": "\U0001f9e9", "name": "Algo", "keywords": ["algo"]},
    "pm": {"icon": "\U0001f3af", "name": "PM", "keywords": ["agile", "jira", "jd", "ticket"]},
    "plugin": {"icon": "\U0001f50c", "name": "Plugin", "keywords": ["sisyphus", "council", "calendar", "frontend-design"]},
    "misc": {"icon": "\u2728", "name": "Misc", "keywords": []},
}


def load_stats():
    """Load stats from JSON file"""
    if STATS_FILE.exists():
        with open(STATS_FILE) as f:
            return json.load(f)
    return {"version": 1, "lastUpdated": datetime.now().strftime("%Y-%m-%d"), "totalUses": 0, "skills": {}}


def save_stats(stats):
    """Save stats to JSON file"""
    stats["lastUpdated"] = datetime.now().strftime("%Y-%m-%d")
    STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)


def get_rarity(uses):
    """Get rarity stars based on usage count"""
    if uses >= 100: return "\u2b50\u2b50\u2b50\u2b50\u2b50"
    if uses >= 50: return "\u2b50\u2b50\u2b50\u2b50"
    if uses >= 20: return "\u2b50\u2b50\u2b50"
    if uses >= 5: return "\u2b50\u2b50"
    if uses >= 1: return "\u2b50"
    return "\u2753"


def calc_level(uses):
    """Calculate level from usage count: Level = floor(sqrt(uses * 10))"""
    return max(1, int(math.sqrt(uses * 10))) if uses > 0 else 0


def format_last_used(date_str):
    """Format last used date as relative time"""
    if not date_str:
        return "Never"
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        diff = (today - date).days
        if diff == 0: return "Today"
        if diff == 1: return "Yesterday"
        if diff < 7: return f"{diff}d ago"
        if diff < 30: return f"{diff // 7}w ago"
        return f"{diff // 30}mo ago"
    except (ValueError, TypeError):
        return date_str


def parse_skill_md(skill_file):
    """Parse SKILL.md file and extract metadata"""
    try:
        with open(skill_file) as f:
            content = f.read()

        description = ""
        match = re.search(r'description:\s*["\']?([^"\'\n]+)', content)
        if match:
            desc = match.group(1)
            desc = desc.split('.')[0][:40]
            description = desc

        return {"description": description}
    except (OSError, UnicodeDecodeError):
        return {"description": ""}


def scan_local_skills():
    """Scan ~/.claude/skills/ directory"""
    skills = {}
    if not SKILLS_DIR.exists():
        return skills

    for skill_dir in SKILLS_DIR.iterdir():
        if skill_dir.is_dir():
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                name = skill_dir.name
                info = parse_skill_md(skill_file)
                skills[name] = {
                    "name": name,
                    "description": info.get("description", ""),
                    "source": "local",
                    "path": str(skill_dir)
                }
    return skills


def scan_plugin_skills():
    """Scan installed plugins for skills"""
    skills = {}
    if not INSTALLED_PLUGINS_FILE.exists():
        return skills

    try:
        with open(INSTALLED_PLUGINS_FILE) as f:
            installed = json.load(f)
    except (OSError, json.JSONDecodeError):
        return skills

    for plugin_name, installs in installed.get("plugins", {}).items():
        for install in installs:
            install_path = Path(install.get("installPath", ""))
            if not install_path.exists():
                continue

            skills_dir = install_path / "skills"
            if skills_dir.exists():
                for skill_dir in skills_dir.iterdir():
                    if skill_dir.is_dir():
                        skill_file = skill_dir / "SKILL.md"
                        if skill_file.exists():
                            base_plugin = plugin_name.split("@")[0]
                            skill_name = skill_dir.name
                            full_name = f"{base_plugin}:{skill_name}" if skill_name != base_plugin else base_plugin

                            info = parse_skill_md(skill_file)
                            skills[full_name] = {
                                "name": full_name,
                                "description": info.get("description", ""),
                                "source": "plugin",
                                "plugin": plugin_name,
                                "path": str(skill_dir)
                            }

            root_skill = install_path / "SKILL.md"
            if root_skill.exists():
                base_plugin = plugin_name.split("@")[0]
                info = parse_skill_md(root_skill)
                if base_plugin not in skills:
                    skills[base_plugin] = {
                        "name": base_plugin,
                        "description": info.get("description", ""),
                        "source": "plugin",
                        "plugin": plugin_name,
                        "path": str(install_path)
                    }

    return skills


def scan_commands():
    """Scan ~/.claude/commands/ directory for .md slash commands"""
    skills = {}
    if not COMMANDS_DIR.exists():
        return skills

    for cmd_file in COMMANDS_DIR.iterdir():
        if cmd_file.is_file() and cmd_file.suffix == ".md":
            name = cmd_file.stem
            info = parse_skill_md(cmd_file)
            skills[name] = {
                "name": name,
                "description": info.get("description", ""),
                "source": "command",
                "path": str(cmd_file)
            }
    return skills


def scan_project_skills():
    """Scan current project's .claude/skills/ directory"""
    skills = {}
    cwd = Path.cwd()
    project_skills_dir = cwd / ".claude" / "skills"

    if not project_skills_dir.exists():
        return skills

    for skill_dir in project_skills_dir.iterdir():
        if skill_dir.is_dir():
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                name = skill_dir.name
                info = parse_skill_md(skill_file)
                skills[f"project:{name}"] = {
                    "name": name,
                    "description": info.get("description", ""),
                    "source": "project",
                    "path": str(skill_dir)
                }
    return skills


def scan_all_skills():
    """Scan all skill sources and merge (local > commands > plugins > project)"""
    all_skills = {}

    local = scan_local_skills()
    all_skills.update(local)

    commands = scan_commands()
    for name, info in commands.items():
        if name not in all_skills:
            all_skills[name] = info

    plugins = scan_plugin_skills()
    for name, info in plugins.items():
        if name not in all_skills:
            all_skills[name] = info

    project = scan_project_skills()
    for name, info in project.items():
        if name not in all_skills:
            all_skills[name] = info

    return all_skills


def get_category(skill_name):
    """Get category for a skill based on keywords"""
    skill_lower = skill_name.lower()

    for cat_id, cat_info in CATEGORIES.items():
        if cat_id == "misc":
            continue
        for keyword in cat_info.get("keywords", []):
            if keyword in skill_lower:
                return cat_id, cat_info

    return "misc", CATEGORIES["misc"]


def render_compact(num, skill_name, skill_info, stats_info):
    """Render compact card (one line)"""
    uses = stats_info.get("uses", 0)
    rarity = get_rarity(uses)
    level = calc_level(uses)
    pinned = "[P]" if stats_info.get("pinned") else ""
    source = skill_info.get("source", "")
    source_icon = {"local": "", "plugin": "\U0001f50c", "project": "\U0001f4c2", "command": "\U0001f4dc"}.get(source, "")

    display_name = skill_name[:24]
    return f"  {rarity} /{display_name:<24} Lv.{level:>2} {uses:>3}x {source_icon}{pinned}"


def render_category_header(cat_id, cat_info, skills_in_cat, stats):
    """Render category header"""
    total = len(skills_in_cat)
    used = len([s for s in skills_in_cat if stats.get("skills", {}).get(s, {}).get("uses", 0) > 0])
    total_level = sum(calc_level(stats.get("skills", {}).get(s, {}).get("uses", 0)) for s in skills_in_cat)

    return f"\n{cat_info['icon']} {cat_info['name']} ({used}/{total}) Lv.{total_level}"


def render_stats_summary(skills, stats):
    """Render stats summary"""
    total_skills = len(skills)
    discovered = len([s for s in skills if stats.get("skills", {}).get(s, {}).get("uses", 0) > 0])
    total_uses = sum(s.get("uses", 0) for s in stats.get("skills", {}).values())
    total_level = sum(calc_level(s.get("uses", 0)) for s in stats.get("skills", {}).values())

    local_count = len([s for s in skills.values() if s.get("source") == "local"])
    command_count = len([s for s in skills.values() if s.get("source") == "command"])
    plugin_count = len([s for s in skills.values() if s.get("source") == "plugin"])
    project_count = len([s for s in skills.values() if s.get("source") == "project"])

    skill_items = stats.get("skills", {}).items()
    most_used = max(skill_items, key=lambda x: x[1].get("uses", 0)) if skill_items else ("None", {"uses": 0})
    most_used_name = most_used[0]
    most_used_count = most_used[1].get("uses", 0)

    rarity_dist = {"\u2b50\u2b50\u2b50\u2b50\u2b50": 0, "\u2b50\u2b50\u2b50\u2b50": 0, "\u2b50\u2b50\u2b50": 0, "\u2b50\u2b50": 0, "\u2b50": 0}
    for s in stats.get("skills", {}).values():
        r = get_rarity(s.get("uses", 0))
        if r in rarity_dist:
            rarity_dist[r] += 1

    w = 55
    lines = [
        f"\n\U0001f4ca Skillbook Stats",
        f"{'━' * w}",
        f"\U0001f4da Total Skills  | {total_skills} (Discovered: {discovered}, {discovered*100//max(total_skills,1)}%)",
        f"   Local: {local_count} | Commands: {command_count} | Plugins: {plugin_count} | Project: {project_count}",
        f"\U0001f525 Total Uses    | {total_uses}x",
        f"\U0001f451 Most Used     | /{most_used_name} ({most_used_count}x)",
        f"\U0001f4c8 Total Level   | Lv.{total_level}",
        f"\u2b50 Rarity Dist   | \u2b50\u2b50\u2b50\u2b50\u2b50 {rarity_dist[chr(11088)*5]} | \u2b50\u2b50\u2b50\u2b50 {rarity_dist[chr(11088)*4]} | \u2b50\u2b50\u2b50 {rarity_dist[chr(11088)*3]}",
        f"{'━' * w}",
    ]
    return "\n".join(lines)


def pin_skill(skill_name, stats):
    """Toggle pin for a skill"""
    if skill_name not in stats["skills"]:
        stats["skills"][skill_name] = {"uses": 0, "lastUsed": None, "pinned": False}

    stats["skills"][skill_name]["pinned"] = not stats["skills"][skill_name].get("pinned", False)
    save_stats(stats)

    status = "pinned" if stats["skills"][skill_name]["pinned"] else "unpinned"
    return f"\U0001f4cc /{skill_name} {status}"


def increment_usage(skill_name, stats):
    """Increment usage count for a skill"""
    if skill_name not in stats["skills"]:
        stats["skills"][skill_name] = {"uses": 0, "lastUsed": None, "pinned": False}

    old_level = calc_level(stats["skills"][skill_name]["uses"])
    stats["skills"][skill_name]["uses"] += 1
    stats["skills"][skill_name]["lastUsed"] = datetime.now().strftime("%Y-%m-%d")
    stats["totalUses"] = stats.get("totalUses", 0) + 1
    new_level = calc_level(stats["skills"][skill_name]["uses"])

    save_stats(stats)

    if new_level > old_level:
        return f"\U0001f389 /{skill_name} Level Up! Lv.{old_level} \u2192 Lv.{new_level}"
    return None


def main(args=None):
    args = args or sys.argv[1:]

    # Install/uninstall/status subcommands (handled before dashboard/terminal routing)
    if args and args[0].lower() == "install":
        from installer import install
        install()
        return

    if args and args[0].lower() == "uninstall":
        from installer import uninstall
        purge = "--purge" in args
        uninstall(purge=purge)
        return

    if args and args[0].lower() == "status":
        from installer import status
        status()
        return

    # Terminal mode - explicit text output
    if args and args[0].lower() in ["terminal", "term", "text", "cli"]:
        args = args[1:]
    # Default: open dashboard
    elif not args or args[0].lower() in ["dashboard", "dash", "visual", "web"]:
        dashboard_script = Path(__file__).parent / "skillbook_dashboard.py"
        if dashboard_script.exists():
            subprocess.run([sys.executable, str(dashboard_script)])
        else:
            print(f"\u274c Dashboard script not found at {dashboard_script}", file=sys.stderr)
            print("   Try reinstalling: /plugin install skillbook", file=sys.stderr)
        return

    stats = load_stats()
    skills = scan_all_skills()

    for skill_name in stats.get("skills", {}).keys():
        if skill_name not in skills:
            skills[skill_name] = {"name": skill_name, "description": "", "source": "stats"}

    filter_cat = None
    show_stats = False
    pinned_only = False
    pin_skill_name = None
    add_usage = None
    show_all = True
    used_only = False

    if args:
        cmd = args[0].lower()
        if cmd in ["stats", "summary"]:
            show_stats = True
        elif cmd in ["pinned", "favorites"]:
            pinned_only = True
        elif cmd in ["used", "discovered"]:
            show_all = False
            used_only = True
        elif cmd == "pin" and len(args) > 1:
            pin_skill_name = args[1]
        elif cmd == "use" and len(args) > 1:
            add_usage = args[1]
        elif cmd in CATEGORIES:
            filter_cat = cmd
        else:
            for cat_id, cat_info in CATEGORIES.items():
                if cmd == cat_info["name"].lower():
                    filter_cat = cat_id
                    break

    if pin_skill_name:
        print(pin_skill(pin_skill_name, stats))
        return

    if add_usage:
        result = increment_usage(add_usage, stats)
        if result:
            print(result)
        else:
            print(f"\u2713 /{add_usage} usage recorded")
        return

    if show_stats:
        print(render_stats_summary(skills, stats))
        return

    all_skills = sorted(skills.keys())
    skill_nums = {s: i+1 for i, s in enumerate(all_skills)}

    output = []

    if pinned_only:
        output.append("\n\U0001f4cc Pinned Skills")
        output.append("\u2501" * 50)
        for skill_name in all_skills:
            stats_info = stats.get("skills", {}).get(skill_name, {})
            if stats_info.get("pinned"):
                output.append(render_compact(skill_nums[skill_name], skill_name, skills[skill_name], stats_info))
    else:
        for cat_id, cat_info in CATEGORIES.items():
            if filter_cat and cat_id != filter_cat:
                continue

            skills_in_cat = [s for s in all_skills if get_category(s)[0] == cat_id]
            if not skills_in_cat:
                continue

            if not show_all:
                used_skills = [s for s in skills_in_cat if stats.get("skills", {}).get(s, {}).get("uses", 0) > 0]
                if not used_skills:
                    continue
                skills_to_show = used_skills
            else:
                skills_to_show = skills_in_cat

            output.append(render_category_header(cat_id, cat_info, skills_in_cat, stats))

            for skill_name in skills_to_show:
                stats_info = stats.get("skills", {}).get(skill_name, {})
                output.append(render_compact(skill_nums[skill_name], skill_name, skills.get(skill_name, {"description": ""}), stats_info))

    if not show_stats and not pinned_only:
        total = len(skills)
        used_count = len([s for s in skills if stats.get("skills", {}).get(s, {}).get("uses", 0) > 0])
        local_count = len([s for s in skills.values() if s.get("source") == "local"])
        command_count = len([s for s in skills.values() if s.get("source") == "command"])
        plugin_count = len([s for s in skills.values() if s.get("source") == "plugin"])
        if used_only:
            output.append(f"\n\U0001f4a1 Discovered: {used_count} | /skillbook for all")
        else:
            output.append(f"\n\U0001f4a1 Local: {local_count} | Commands: {command_count} | Plugins: {plugin_count} | Used: {used_count}/{total}")

    print("\n".join(output))


if __name__ == "__main__":
    main()
