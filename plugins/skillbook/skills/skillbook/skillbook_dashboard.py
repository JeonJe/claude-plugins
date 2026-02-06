#!/usr/bin/env python3
"""
Skillbook Dashboard v2.0 - Enhanced with Detail Modal, Search, Workflows
"""

import json
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
OUTPUT_DIR = _config.get("outputDir", CLAUDE_DIR / "skillbook")
OUTPUT_FILE = OUTPUT_DIR / "dashboard.html"

# Categories with colors and workflows
CATEGORIES = {
    "git": {"icon": "📁", "name": "Git", "color": "#f97316", "skills": ["commit", "pr", "branch-cleanup", "worktree", "oh-my-claude-sisyphus:git-master"]},
    "code": {"icon": "💻", "name": "Code", "color": "#8b5cf6", "skills": ["code-review", "tdd", "build-fix", "refactor-clean", "restructure", "algo-review"]},
    "test": {"icon": "🧪", "name": "Test", "color": "#06b6d4", "skills": ["test", "e2e", "test-coverage"]},
    "docs": {"icon": "📝", "name": "Docs", "color": "#84cc16", "skills": ["update-docs", "update-codemaps", "doc-polish"]},
    "plan": {"icon": "📋", "name": "Plan", "color": "#eab308", "skills": ["plan-quick", "issue", "clarify", "oh-my-claude-sisyphus:prometheus", "oh-my-claude-sisyphus:plan"]},
    "study": {"icon": "📚", "name": "Study", "color": "#3b82f6", "skills": ["study", "study-wrap", "gg", "interview", "algo-learn"]},
    "resume": {"icon": "📄", "name": "Resume", "color": "#ec4899", "skills": ["resume-write", "resume-review", "resume-tailor", "biz-impact"]},
    "algo": {"icon": "🧩", "name": "Algo", "color": "#14b8a6", "skills": ["algo-start", "algo-save", "algo-learn", "algo-review"]},
    "pm": {"icon": "🎯", "name": "PM", "color": "#f43f5e", "skills": ["agile-pm", "jira-ticket", "jd-update"]},
    "plugin": {"icon": "🔌", "name": "Plugin", "color": "#10b981", "skills": ["agent-council", "google-calendar", "session-wrap", "frontend-design", "oh-my-claude-sisyphus:frontend-ui-ux", "oh-my-claude-sisyphus:ultrawork", "oh-my-claude-sisyphus:deepinit", "oh-my-claude-sisyphus:release"]},
    "misc": {"icon": "✨", "name": "Misc", "color": "#a855f7", "skills": ["skillbook", "daily", "work-log", "sayno", "skill-audit", "para-audit", "para-naming"]},
}

# Skill workflows (recommended sequences)
WORKFLOWS = [
    {"name": "Algorithm Practice", "skills": ["algo-start", "algo-learn", "algo-review", "algo-save"], "icon": "🧩"},
    {"name": "Learning Cycle", "skills": ["study", "gg", "study-wrap"], "icon": "📚"},
    {"name": "Code Quality", "skills": ["code-review", "refactor-clean", "test-coverage"], "icon": "💻"},
    {"name": "Job Prep", "skills": ["jd-update", "interview", "biz-impact"], "icon": "🎯"},
    {"name": "Documentation", "skills": ["doc-polish", "update-docs", "update-codemaps"], "icon": "📝"},
]

# Achievements
ACHIEVEMENTS = [
    {"id": "first_blood", "name": "First Blood", "desc": "Use your first skill", "icon": "🩸", "condition": lambda stats: stats.get("totalUses", 0) >= 1},
    {"id": "explorer", "name": "Explorer", "desc": "Discover 10 skills", "icon": "🧭", "condition": lambda stats: len([s for s in stats.get("skills", {}).values() if s.get("uses", 0) > 0]) >= 10},
    {"id": "master_10", "name": "Dedicated", "desc": "Use any skill 10+ times", "icon": "🔥", "condition": lambda stats: any(s.get("uses", 0) >= 10 for s in stats.get("skills", {}).values())},
    {"id": "master_50", "name": "Expert", "desc": "Use any skill 50+ times", "icon": "👑", "condition": lambda stats: any(s.get("uses", 0) >= 50 for s in stats.get("skills", {}).values())},
    {"id": "polyglot", "name": "Polyglot", "desc": "Use skills from 5+ categories", "icon": "🌍", "condition": lambda stats: len(set(get_category(s)[0] for s in stats.get("skills", {}).keys() if stats["skills"][s].get("uses", 0) > 0)) >= 5},
    {"id": "daily_driver", "name": "Daily Driver", "desc": "100+ total uses", "icon": "🚗", "condition": lambda stats: stats.get("totalUses", 0) >= 100},
    {"id": "study_master", "name": "Study Master", "desc": "Use gg 20+ times", "icon": "📖", "condition": lambda stats: stats.get("skills", {}).get("gg", {}).get("uses", 0) >= 20},
    {"id": "algo_warrior", "name": "Algo Warrior", "desc": "Use algo-start 10+ times", "icon": "⚔️", "condition": lambda stats: stats.get("skills", {}).get("algo-start", {}).get("uses", 0) >= 10},
]

def load_stats():
    if STATS_FILE.exists():
        with open(STATS_FILE) as f:
            return json.load(f)
    return {"version": 1, "lastUpdated": datetime.now().strftime("%Y-%m-%d"), "totalUses": 0, "skills": {}}

def get_category(skill_name):
    for cat_id, cat_info in CATEGORIES.items():
        if skill_name in cat_info["skills"]:
            return cat_id, cat_info
    # Keyword-based fallback
    skill_lower = skill_name.lower()
    for cat_id, cat_info in CATEGORIES.items():
        for skill in cat_info["skills"]:
            if skill in skill_lower or skill_lower in skill:
                return cat_id, cat_info
    return "misc", CATEGORIES["misc"]

def calc_level(uses):
    import math
    return max(1, int(math.sqrt(uses * 10))) if uses > 0 else 0

def get_rarity_stars(uses):
    if uses >= 100: return 5
    if uses >= 50: return 4
    if uses >= 20: return 3
    if uses >= 5: return 2
    if uses >= 1: return 1
    return 0

def parse_skill_md(skill_file):
    """Parse SKILL.md file and extract full metadata"""
    try:
        with open(skill_file, encoding='utf-8') as f:
            content = f.read()

        result = {
            "description": "",
            "fullContent": content,
            "useCases": [],
            "triggers": [],
            "dontUse": [],
            "workflow": "",
        }

        # Extract description from frontmatter
        match = re.search(r'description:\s*["\']?([^"\'\n]+)', content)
        if match:
            result["description"] = match.group(1)

        # Extract Use Cases section
        use_case_match = re.search(r'## Use Cases?\s*\n(.*?)(?=\n## |\n---|\Z)', content, re.DOTALL)
        if use_case_match:
            cases = re.findall(r'\*\*(\d+\.\s*[^*]+)\*\*\s*\n-\s*Input:\s*([^\n]+)\s*\n-\s*Action:\s*([^\n]+)\s*\n-\s*Output:\s*([^\n]+)', use_case_match.group(1))
            for case in cases:
                result["useCases"].append({
                    "title": case[0].strip(),
                    "input": case[1].strip(),
                    "action": case[2].strip(),
                    "output": case[3].strip()
                })

        # Extract triggers/keywords
        trigger_match = re.search(r'(?:Trigger|Use when|Keywords?).*?[:\-]\s*([^\n]+)', content, re.IGNORECASE)
        if trigger_match:
            triggers = re.findall(r'"([^"]+)"', trigger_match.group(1))
            result["triggers"] = triggers[:5]  # Limit to 5

        # Extract "Don't use when"
        dont_use_match = re.search(r"(?:Don't use when|Don't Use When|anti-triggers?).*?\n(.*?)(?=\n## |\n---|\Z)", content, re.DOTALL | re.IGNORECASE)
        if dont_use_match:
            lines = [l.strip().lstrip('- ') for l in dont_use_match.group(1).split('\n') if l.strip().startswith('-')]
            result["dontUse"] = lines[:4]

        # Extract workflow summary
        workflow_match = re.search(r'## Workflow\s*\n(.*?)(?=\n## |\n---|\Z)', content, re.DOTALL)
        if workflow_match:
            result["workflow"] = workflow_match.group(1).strip()[:500]

        return result
    except Exception as e:
        return {"description": "", "fullContent": "", "useCases": [], "triggers": [], "dontUse": [], "workflow": ""}

def scan_local_skills():
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
                    "path": str(skill_file),
                    "useCases": info.get("useCases", []),
                    "triggers": info.get("triggers", []),
                    "dontUse": info.get("dontUse", []),
                    "workflow": info.get("workflow", ""),
                }
    return skills

def scan_commands():
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
                "path": str(cmd_file),
                "useCases": info.get("useCases", []),
                "triggers": info.get("triggers", []),
                "dontUse": info.get("dontUse", []),
                "workflow": info.get("workflow", ""),
            }
    return skills

def scan_plugin_skills():
    skills = {}
    plugins_file = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    if not plugins_file.exists():
        return skills
    try:
        with open(plugins_file) as f:
            installed = json.load(f)
    except:
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
                                "path": str(skill_file),
                                "useCases": info.get("useCases", []),
                                "triggers": info.get("triggers", []),
                                "dontUse": info.get("dontUse", []),
                                "workflow": info.get("workflow", ""),
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
                        "path": str(root_skill),
                        "useCases": info.get("useCases", []),
                        "triggers": info.get("triggers", []),
                        "dontUse": info.get("dontUse", []),
                        "workflow": info.get("workflow", ""),
                    }
    return skills

def get_pokemon_id(skill_name):
    import hashlib
    hash_val = int(hashlib.md5(skill_name.encode()).hexdigest(), 16)
    return (hash_val % 898) + 1

def scan_skills():
    all_skills = {}
    all_skills.update(scan_local_skills())
    for name, info in scan_commands().items():
        if name not in all_skills:
            all_skills[name] = info
    for name, info in scan_plugin_skills().items():
        if name not in all_skills:
            all_skills[name] = info
    return all_skills

def get_recommendations(skills_data, stats):
    """Get personalized skill recommendations"""
    recommendations = []

    # 1. Unused skills in active categories
    active_cats = set()
    for s in stats.get("skills", {}).values():
        if s.get("uses", 0) > 0:
            for skill_name in stats.get("skills", {}).keys():
                if stats["skills"][skill_name].get("uses", 0) > 0:
                    cat_id, _ = get_category(skill_name)
                    active_cats.add(cat_id)

    for skill in skills_data:
        if skill["uses"] == 0 and skill["category"] in active_cats:
            recommendations.append({
                "skill": skill["name"],
                "reason": f"You use {skill['categoryName']} skills - try this one!",
                "priority": 1
            })

    # 2. Workflow completion suggestions
    for wf in WORKFLOWS:
        used = [s for s in wf["skills"] if stats.get("skills", {}).get(s, {}).get("uses", 0) > 0]
        unused = [s for s in wf["skills"] if stats.get("skills", {}).get(s, {}).get("uses", 0) == 0]
        if len(used) > 0 and len(unused) > 0:
            recommendations.append({
                "skill": unused[0],
                "reason": f"Complete '{wf['name']}' workflow!",
                "priority": 2
            })

    # Sort by priority and limit
    recommendations.sort(key=lambda x: x["priority"])
    return recommendations[:3]

def generate_dashboard():
    stats = load_stats()
    skills = scan_skills()

    # Merge stats skills
    for skill_name in stats.get("skills", {}).keys():
        if skill_name not in skills:
            skills[skill_name] = {"name": skill_name, "description": "", "source": "stats", "useCases": [], "triggers": [], "dontUse": [], "workflow": ""}

    # Prepare data for JavaScript
    skills_data = []
    for name, info in skills.items():
        # Skip project: prefixed duplicates
        if name.startswith("project:"):
            continue
        cat_id, cat_info = get_category(name)
        stat = stats.get("skills", {}).get(name, {})
        uses = stat.get("uses", 0)
        skills_data.append({
            "name": name,
            "description": info.get("description", ""),
            "category": cat_id,
            "categoryName": cat_info["name"],
            "categoryIcon": cat_info["icon"],
            "categoryColor": cat_info["color"],
            "uses": uses,
            "level": calc_level(uses),
            "stars": get_rarity_stars(uses),
            "pinned": stat.get("pinned", False),
            "lastUsed": stat.get("lastUsed", None),
            "pokemonId": get_pokemon_id(name),
            "source": info.get("source", "unknown"),
            "useCases": info.get("useCases", []),
            "triggers": info.get("triggers", []),
            "dontUse": info.get("dontUse", []),
            "workflow": info.get("workflow", ""),
            "path": str(Path(info.get("path", "")).relative_to(HOME)) if info.get("path") else "",
        })

    # Category stats
    category_stats = {}
    for cat_id, cat_info in CATEGORIES.items():
        cat_skills = [s for s in skills_data if s["category"] == cat_id]
        total_uses = sum(s["uses"] for s in cat_skills)
        total_level = sum(s["level"] for s in cat_skills)
        discovered = len([s for s in cat_skills if s["uses"] > 0])
        category_stats[cat_id] = {
            "name": cat_info["name"],
            "icon": cat_info["icon"],
            "color": cat_info["color"],
            "totalUses": total_uses,
            "totalLevel": total_level,
            "total": len(cat_skills),
            "discovered": discovered
        }

    # Achievements check
    unlocked_achievements = []
    for ach in ACHIEVEMENTS:
        if ach["condition"](stats):
            unlocked_achievements.append({"id": ach["id"], "name": ach["name"], "desc": ach["desc"], "icon": ach["icon"]})

    # Recommendations
    recommendations = get_recommendations(skills_data, stats)

    # Usage history for trend (last 7 days simulation based on lastUsed)
    today = datetime.now().date()
    usage_trend = []
    for i in range(6, -1, -1):
        date = today - timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        count = sum(1 for s in stats.get("skills", {}).values() if s.get("lastUsed") == date_str)
        usage_trend.append({"date": date.strftime("%m/%d"), "count": count})

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Skillbook Dashboard v2</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js" crossorigin="anonymous"></script>
    <script src="https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js" crossorigin="anonymous"></script>
    <style>
        :root {{
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-card: #334155;
            --bg-modal: #1e293b;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent: #3b82f6;
            --gold: #fbbf24;
            --silver: #9ca3af;
            --bronze: #d97706;
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
        }}

        .container {{ max-width: 1600px; margin: 0 auto; padding: 2rem; }}

        header {{ text-align: center; margin-bottom: 2rem; }}
        header h1 {{
            font-size: 2.5rem;
            background: linear-gradient(135deg, #fbbf24, #f97316, #ef4444);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }}

        .stats-bar {{
            display: flex;
            justify-content: center;
            gap: 2rem;
            margin-top: 1rem;
            flex-wrap: wrap;
        }}

        .stat-item {{ text-align: center; }}
        .stat-value {{ font-size: 1.5rem; font-weight: bold; color: var(--gold); }}
        .stat-label {{ color: var(--text-secondary); font-size: 0.8rem; }}

        /* Search & Filters */
        .controls {{
            display: flex;
            gap: 1rem;
            margin-bottom: 1.5rem;
            flex-wrap: wrap;
            align-items: center;
        }}

        .search-box {{
            flex: 1;
            min-width: 200px;
            padding: 0.75rem 1rem;
            border: 2px solid var(--bg-card);
            border-radius: 0.5rem;
            background: var(--bg-secondary);
            color: var(--text-primary);
            font-size: 1rem;
        }}
        .search-box:focus {{ outline: none; border-color: var(--accent); }}

        .filter-group {{ display: flex; gap: 0.5rem; flex-wrap: wrap; }}
        .filter-btn {{
            padding: 0.5rem 1rem;
            border: none;
            border-radius: 0.5rem;
            background: var(--bg-card);
            color: var(--text-secondary);
            cursor: pointer;
            transition: all 0.2s;
            font-size: 0.875rem;
        }}
        .filter-btn:hover, .filter-btn.active {{
            background: var(--accent);
            color: var(--text-primary);
        }}

        .sort-select {{
            padding: 0.5rem 1rem;
            border: none;
            border-radius: 0.5rem;
            background: var(--bg-card);
            color: var(--text-primary);
            cursor: pointer;
        }}

        /* Dashboard Grid */
        .dashboard-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}
        @media (max-width: 1200px) {{ .dashboard-grid {{ grid-template-columns: 1fr 1fr; }} }}
        @media (max-width: 800px) {{ .dashboard-grid {{ grid-template-columns: 1fr; }} }}

        .panel {{
            background: var(--bg-secondary);
            border-radius: 1rem;
            padding: 1.25rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
        }}
        .panel-title {{
            font-size: 1rem;
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            color: var(--text-secondary);
        }}

        /* Achievements */
        .achievements {{
            display: flex;
            gap: 0.75rem;
            flex-wrap: wrap;
        }}
        .achievement {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 0.75rem;
            background: var(--bg-card);
            border-radius: 0.5rem;
            font-size: 0.8rem;
        }}
        .achievement.locked {{ opacity: 0.4; filter: grayscale(1); }}
        .achievement-icon {{ font-size: 1.2rem; }}

        /* Recommendations */
        .recommendations {{
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }}
        .rec-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.75rem;
            background: var(--bg-card);
            border-radius: 0.5rem;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .rec-item:hover {{ background: var(--accent); }}
        .rec-skill {{ font-weight: 600; }}
        .rec-reason {{ font-size: 0.75rem; color: var(--text-secondary); }}

        /* Workflows */
        .workflows {{
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }}
        .workflow {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem;
            background: var(--bg-card);
            border-radius: 0.5rem;
            font-size: 0.8rem;
            overflow-x: auto;
        }}
        .workflow-step {{
            padding: 0.25rem 0.5rem;
            background: var(--bg-primary);
            border-radius: 0.25rem;
            white-space: nowrap;
        }}
        .workflow-step.used {{ background: var(--accent); }}
        .workflow-arrow {{ color: var(--text-secondary); }}

        /* Skill Cards */
        .skill-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 1rem;
            margin-top: 1rem;
        }}

        .skill-card {{
            background: var(--bg-card);
            border-radius: 1rem;
            padding: 1rem;
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
            cursor: pointer;
            border: 2px solid transparent;
        }}
        .skill-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 12px 24px -4px rgba(0, 0, 0, 0.4);
            border-color: var(--accent);
        }}
        .skill-card.undiscovered {{ opacity: 0.5; filter: grayscale(0.6); }}
        .skill-card.undiscovered:hover {{ opacity: 0.8; filter: grayscale(0.3); }}

        .pokemon-image-container {{
            width: 100%;
            height: 100px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 0.5rem;
            margin-bottom: 0.5rem;
            position: relative;
        }}
        .pokemon-image {{ max-width: 80px; max-height: 80px; transition: transform 0.3s ease; filter: drop-shadow(0 4px 8px rgba(0,0,0,0.3)); }}
        .skill-card:hover .pokemon-image {{ transform: scale(1.1); }}
        .skill-card.undiscovered .pokemon-image {{ filter: brightness(0) grayscale(1); }}
        .pokemon-id {{ position: absolute; top: 0.25rem; left: 0.5rem; font-size: 0.65rem; color: var(--text-secondary); opacity: 0.6; }}

        .card-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem; }}
        .skill-name {{ font-size: 0.95rem; font-weight: 600; }}
        .skill-level {{ background: linear-gradient(135deg, var(--gold), var(--bronze)); padding: 0.2rem 0.5rem; border-radius: 1rem; font-size: 0.7rem; font-weight: bold; color: #000; }}
        .skill-level.zero {{ background: var(--bg-primary); color: var(--text-secondary); }}

        .stars {{ color: var(--gold); font-size: 0.75rem; margin-bottom: 0.25rem; }}
        .stars.empty {{ color: var(--bg-primary); }}

        .skill-desc {{ color: var(--text-secondary); font-size: 0.75rem; margin-bottom: 0.5rem; min-height: 2rem; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}

        .card-footer {{ display: flex; justify-content: space-between; align-items: center; padding-top: 0.5rem; border-top: 1px solid rgba(255,255,255,0.1); }}
        .category-badge {{ padding: 0.2rem 0.4rem; border-radius: 0.4rem; font-size: 0.65rem; font-weight: 500; }}
        .uses-count {{ font-size: 0.75rem; color: var(--text-secondary); }}
        .uses-count strong {{ color: var(--text-primary); }}

        .exp-bar {{ width: 100%; height: 3px; background: var(--bg-primary); border-radius: 2px; margin-top: 0.5rem; overflow: hidden; }}
        .exp-fill {{ height: 100%; border-radius: 2px; transition: width 0.5s ease; }}

        .pinned-badge {{ position: absolute; top: 0.5rem; right: 0.5rem; font-size: 0.9rem; }}
        .source-badge {{ position: absolute; bottom: 0.5rem; right: 0.5rem; font-size: 0.6rem; padding: 0.15rem 0.3rem; border-radius: 0.25rem; background: var(--bg-primary); color: var(--text-secondary); }}

        /* Modal */
        .modal-overlay {{
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.8);
            z-index: 1000;
            align-items: center;
            justify-content: center;
            padding: 2rem;
        }}
        .modal-overlay.show {{ display: flex; }}

        .modal {{
            background: var(--bg-modal);
            border-radius: 1rem;
            max-width: 700px;
            width: 100%;
            max-height: 85vh;
            overflow-y: auto;
            position: relative;
            animation: modalIn 0.2s ease;
        }}
        @keyframes modalIn {{ from {{ opacity: 0; transform: scale(0.95); }} to {{ opacity: 1; transform: scale(1); }} }}

        .modal-close {{
            position: absolute;
            top: 1rem; right: 1rem;
            background: none; border: none;
            color: var(--text-secondary);
            font-size: 1.5rem;
            cursor: pointer;
            z-index: 10;
        }}
        .modal-close:hover {{ color: var(--text-primary); }}

        .modal-header {{
            padding: 1.5rem;
            display: flex;
            gap: 1.5rem;
            align-items: flex-start;
            border-bottom: 1px solid var(--bg-card);
        }}
        .modal-pokemon {{ width: 120px; height: 120px; background: var(--bg-card); border-radius: 1rem; display: flex; align-items: center; justify-content: center; }}
        .modal-pokemon img {{ max-width: 100px; max-height: 100px; }}
        .modal-info {{ flex: 1; }}
        .modal-title {{ font-size: 1.5rem; margin-bottom: 0.5rem; }}
        .modal-meta {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 0.5rem; }}
        .modal-meta-item {{ font-size: 0.85rem; color: var(--text-secondary); }}
        .modal-desc {{ color: var(--text-secondary); font-size: 0.9rem; }}

        .modal-body {{ padding: 1.5rem; }}
        .modal-section {{ margin-bottom: 1.5rem; }}
        .modal-section-title {{ font-size: 0.9rem; font-weight: 600; margin-bottom: 0.75rem; color: var(--gold); display: flex; align-items: center; gap: 0.5rem; }}

        .use-case {{
            background: var(--bg-card);
            padding: 0.75rem;
            border-radius: 0.5rem;
            margin-bottom: 0.5rem;
        }}
        .use-case-title {{ font-weight: 600; margin-bottom: 0.5rem; font-size: 0.85rem; }}
        .use-case-item {{ font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 0.25rem; }}
        .use-case-item strong {{ color: var(--accent); }}

        .tag-list {{ display: flex; gap: 0.5rem; flex-wrap: wrap; }}
        .tag {{ padding: 0.25rem 0.5rem; background: var(--bg-card); border-radius: 0.25rem; font-size: 0.75rem; }}
        .tag.danger {{ background: #7f1d1d; color: #fca5a5; }}

        .modal-actions {{
            padding: 1rem 1.5rem;
            border-top: 1px solid var(--bg-card);
            display: flex;
            gap: 1rem;
        }}
        .modal-btn {{
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 0.5rem;
            cursor: pointer;
            font-size: 0.9rem;
            transition: all 0.2s;
        }}
        .modal-btn.primary {{ background: var(--accent); color: white; }}
        .modal-btn.primary:hover {{ background: #2563eb; }}
        .modal-btn.secondary {{ background: var(--bg-card); color: var(--text-primary); }}

        /* Chart container */
        .chart-container {{ position: relative; height: 200px; }}

        /* Category progress */
        .category-progress {{ margin-bottom: 0.75rem; }}
        .category-header {{ display: flex; justify-content: space-between; margin-bottom: 0.2rem; font-size: 0.8rem; }}
        .progress-bar {{ height: 6px; background: var(--bg-card); border-radius: 3px; overflow: hidden; }}
        .progress-fill {{ height: 100%; border-radius: 3px; transition: width 0.5s ease; }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Skillbook</h1>
            <p style="color: var(--text-secondary);">Claude Code Skill Dashboard</p>
            <div class="stats-bar">
                <div class="stat-item">
                    <div class="stat-value" id="total-discovered">0</div>
                    <div class="stat-label">Discovered</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" id="total-skills">0</div>
                    <div class="stat-label">Total</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" id="total-uses">0</div>
                    <div class="stat-label">Uses</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" id="total-level">0</div>
                    <div class="stat-label">Level</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" id="achievements-count">0</div>
                    <div class="stat-label">Badges</div>
                </div>
            </div>
        </header>

        <div class="dashboard-grid">
            <div class="panel">
                <div class="panel-title">🏆 Achievements</div>
                <div class="achievements" id="achievements"></div>
            </div>

            <div class="panel">
                <div class="panel-title">💡 Recommended</div>
                <div class="recommendations" id="recommendations"></div>
            </div>

            <div class="panel">
                <div class="panel-title">🔗 Workflows</div>
                <div class="workflows" id="workflows"></div>
            </div>
        </div>

        <div class="dashboard-grid" style="grid-template-columns: 1fr 1fr;">
            <div class="panel">
                <div class="panel-title">📊 Category Progress</div>
                <div id="category-progress"></div>
            </div>
            <div class="panel">
                <div class="panel-title">📈 Usage Trend (7 days)</div>
                <div class="chart-container">
                    <canvas id="trend-chart"></canvas>
                </div>
            </div>
        </div>

        <div class="panel">
            <div class="panel-title" style="font-size: 1.1rem;">🃏 Skill Cards</div>
            <div class="controls">
                <input type="text" class="search-box" id="search" placeholder="Search skills... (name, description, trigger)">
                <div class="filter-group">
                    <button class="filter-btn active" data-filter="all">All</button>
                    <button class="filter-btn" data-filter="discovered">Discovered</button>
                    <button class="filter-btn" data-filter="pinned">Pinned</button>
                    <button class="filter-btn" data-filter="local">Local</button>
                    <button class="filter-btn" data-filter="command">Commands</button>
                </div>
                <select class="sort-select" id="sort">
                    <option value="uses">Sort: Uses</option>
                    <option value="level">Sort: Level</option>
                    <option value="recent">Sort: Recent</option>
                    <option value="name">Sort: Name</option>
                </select>
            </div>
            <div class="skill-cards" id="skill-cards"></div>
        </div>
    </div>

    <!-- Detail Modal -->
    <div class="modal-overlay" id="modal-overlay">
        <div class="modal" id="modal">
            <button class="modal-close" onclick="closeModal()">&times;</button>
            <div class="modal-header">
                <div class="modal-pokemon" id="modal-pokemon"></div>
                <div class="modal-info">
                    <h2 class="modal-title" id="modal-title"></h2>
                    <div class="modal-meta" id="modal-meta"></div>
                    <p class="modal-desc" id="modal-desc"></p>
                </div>
            </div>
            <div class="modal-body" id="modal-body"></div>
            <div class="modal-actions">
                <button class="modal-btn primary" onclick="copySkillCommand()">📋 Copy Command</button>
                <button class="modal-btn secondary" onclick="closeModal()">Close</button>
            </div>
        </div>
    </div>

    <script>
        const skillsData = {json.dumps(skills_data, ensure_ascii=False)};
        const categoryStats = {json.dumps(category_stats, ensure_ascii=False)};
        const CATEGORIES = {json.dumps({k: {"name": v["name"], "icon": v["icon"], "color": v["color"]} for k, v in CATEGORIES.items()}, ensure_ascii=False)};
        const achievements = {json.dumps(unlocked_achievements, ensure_ascii=False)};
        const allAchievements = {json.dumps([{"id": a["id"], "name": a["name"], "desc": a["desc"], "icon": a["icon"]} for a in ACHIEVEMENTS], ensure_ascii=False)};
        const recommendations = {json.dumps(recommendations, ensure_ascii=False)};
        const workflows = {json.dumps(WORKFLOWS, ensure_ascii=False)};
        const usageTrend = {json.dumps(usage_trend, ensure_ascii=False)};
        const stats = {json.dumps(stats, ensure_ascii=False)};

        let currentSkill = null;

        // Stats
        const totalSkills = skillsData.length;
        const discoveredSkills = skillsData.filter(s => s.uses > 0).length;
        const totalUses = skillsData.reduce((sum, s) => sum + s.uses, 0);
        const totalLevel = skillsData.reduce((sum, s) => sum + s.level, 0);

        document.getElementById('total-skills').textContent = totalSkills;
        document.getElementById('total-discovered').textContent = discoveredSkills;
        document.getElementById('total-uses').textContent = totalUses;
        document.getElementById('total-level').textContent = 'Lv.' + totalLevel;
        document.getElementById('achievements-count').textContent = achievements.length + '/' + allAchievements.length;

        // Achievements
        const achContainer = document.getElementById('achievements');
        allAchievements.forEach(ach => {{
            const unlocked = achievements.find(a => a.id === ach.id);
            achContainer.innerHTML += `
                <div class="achievement ${{unlocked ? '' : 'locked'}}" title="${{ach.desc}}">
                    <span class="achievement-icon">${{ach.icon}}</span>
                    <span>${{ach.name}}</span>
                </div>
            `;
        }});

        // Recommendations
        const recContainer = document.getElementById('recommendations');
        if (recommendations.length === 0) {{
            recContainer.innerHTML = '<p style="color: var(--text-secondary); font-size: 0.85rem;">Keep using skills to get recommendations!</p>';
        }} else {{
            recommendations.forEach(rec => {{
                recContainer.innerHTML += `
                    <div class="rec-item" onclick="openSkillModal('${{rec.skill}}')">
                        <div>
                            <div class="rec-skill">/${{rec.skill}}</div>
                            <div class="rec-reason">${{rec.reason}}</div>
                        </div>
                        <span>→</span>
                    </div>
                `;
            }});
        }}

        // Workflows
        const wfContainer = document.getElementById('workflows');
        workflows.forEach(wf => {{
            const steps = wf.skills.map(s => {{
                const used = stats.skills && stats.skills[s] && stats.skills[s].uses > 0;
                return `<span class="workflow-step ${{used ? 'used' : ''}}">${{s}}</span>`;
            }}).join('<span class="workflow-arrow">→</span>');
            wfContainer.innerHTML += `
                <div class="workflow">
                    <span>${{wf.icon}}</span>
                    ${{steps}}
                </div>
            `;
        }});

        // Category Progress
        const progressContainer = document.getElementById('category-progress');
        Object.entries(categoryStats).forEach(([cat, info]) => {{
            if (info.total === 0) return;
            const percent = Math.round((info.discovered / info.total) * 100);
            progressContainer.innerHTML += `
                <div class="category-progress">
                    <div class="category-header">
                        <span>${{info.icon}} ${{info.name}}</span>
                        <span style="color: var(--text-secondary);">${{info.discovered}}/${{info.total}} | Lv.${{info.totalLevel}}</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${{percent}}%; background: ${{info.color}};"></div>
                    </div>
                </div>
            `;
        }});

        // Trend Chart
        const trendCtx = document.getElementById('trend-chart').getContext('2d');
        new Chart(trendCtx, {{
            type: 'line',
            data: {{
                labels: usageTrend.map(d => d.date),
                datasets: [{{
                    label: 'Skills Used',
                    data: usageTrend.map(d => d.count),
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    fill: true,
                    tension: 0.4
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{
                    y: {{ beginAtZero: true, grid: {{ color: 'rgba(255,255,255,0.05)' }}, ticks: {{ color: '#94a3b8' }} }},
                    x: {{ grid: {{ display: false }}, ticks: {{ color: '#94a3b8' }} }}
                }}
            }}
        }});

        // Skill Cards
        function renderCards(filter = 'all', search = '', sort = 'uses') {{
            const container = document.getElementById('skill-cards');
            let filtered = [...skillsData];

            // Filter
            if (filter === 'discovered') filtered = filtered.filter(s => s.uses > 0);
            else if (filter === 'pinned') filtered = filtered.filter(s => s.pinned);
            else if (filter === 'local') filtered = filtered.filter(s => s.source === 'local');
            else if (filter === 'command') filtered = filtered.filter(s => s.source === 'command');

            // Search
            if (search) {{
                const q = search.toLowerCase();
                filtered = filtered.filter(s =>
                    s.name.toLowerCase().includes(q) ||
                    s.description.toLowerCase().includes(q) ||
                    s.triggers.some(t => t.toLowerCase().includes(q))
                );
            }}

            // Sort
            if (sort === 'uses') filtered.sort((a, b) => b.uses - a.uses);
            else if (sort === 'level') filtered.sort((a, b) => b.level - a.level);
            else if (sort === 'recent') filtered.sort((a, b) => (b.lastUsed || '').localeCompare(a.lastUsed || ''));
            else if (sort === 'name') filtered.sort((a, b) => a.name.localeCompare(b.name));

            // Pinned first
            filtered.sort((a, b) => (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0));

            container.innerHTML = filtered.map(skill => {{
                const stars = '★'.repeat(skill.stars) + '☆'.repeat(5 - skill.stars);
                const expPercent = skill.level > 0 ? Math.min(100, (skill.uses % 10) * 10) : 0;
                const isUndiscovered = skill.uses === 0;
                const pokemonUrl = `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/${{skill.pokemonId}}.png`;
                const paddedId = String(skill.pokemonId).padStart(3, '0');
                const sourceIcon = {{'local': '💾', 'command': '📜', 'plugin': '🔌', 'stats': '📊'}}[skill.source] || '';

                return `
                    <div class="skill-card ${{isUndiscovered ? 'undiscovered' : ''}}"
                         style="border-color: ${{skill.categoryColor}}33;"
                         onclick="openSkillModal('${{skill.name}}')">
                        ${{skill.pinned ? '<div class="pinned-badge">📌</div>' : ''}}
                        <div class="source-badge">${{sourceIcon}} ${{skill.source}}</div>
                        <div class="pokemon-image-container" style="background: linear-gradient(135deg, ${{skill.categoryColor}}15, ${{skill.categoryColor}}05);">
                            <div class="pokemon-id">#${{paddedId}}</div>
                            <img src="${{pokemonUrl}}" class="pokemon-image" loading="lazy"
                                 onerror="this.src='https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${{skill.pokemonId}}.png'">
                        </div>
                        <div class="card-header">
                            <span class="skill-name">/${{skill.name}}</span>
                            <span class="skill-level ${{skill.level === 0 ? 'zero' : ''}}">Lv.${{skill.level}}</span>
                        </div>
                        <div class="stars ${{skill.stars === 0 ? 'empty' : ''}}">${{stars}}</div>
                        <div class="skill-desc">${{skill.description || 'No description'}}</div>
                        <div class="card-footer">
                            <span class="category-badge" style="background: ${{skill.categoryColor}}22; color: ${{skill.categoryColor}};">
                                ${{skill.categoryIcon}} ${{skill.categoryName}}
                            </span>
                            <span class="uses-count"><strong>${{skill.uses}}</strong> uses</span>
                        </div>
                        <div class="exp-bar">
                            <div class="exp-fill" style="width: ${{expPercent}}%; background: ${{skill.categoryColor}};"></div>
                        </div>
                    </div>
                `;
            }}).join('');
        }}

        renderCards();

        // Event listeners
        document.querySelectorAll('.filter-btn').forEach(btn => {{
            btn.addEventListener('click', () => {{
                document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                renderCards(btn.dataset.filter, document.getElementById('search').value, document.getElementById('sort').value);
            }});
        }});

        document.getElementById('search').addEventListener('input', (e) => {{
            const activeFilter = document.querySelector('.filter-btn.active').dataset.filter;
            renderCards(activeFilter, e.target.value, document.getElementById('sort').value);
        }});

        document.getElementById('sort').addEventListener('change', (e) => {{
            const activeFilter = document.querySelector('.filter-btn.active').dataset.filter;
            renderCards(activeFilter, document.getElementById('search').value, e.target.value);
        }});

        // Modal functions
        function openSkillModal(skillName) {{
            currentSkill = skillsData.find(s => s.name === skillName);
            if (!currentSkill) return;

            const pokemonUrl = `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/${{currentSkill.pokemonId}}.png`;

            document.getElementById('modal-pokemon').innerHTML = `<img src="${{pokemonUrl}}" alt="${{currentSkill.name}}">`;
            document.getElementById('modal-title').textContent = '/' + currentSkill.name;
            document.getElementById('modal-meta').innerHTML = `
                <span class="modal-meta-item" style="color: ${{currentSkill.categoryColor}};">${{currentSkill.categoryIcon}} ${{currentSkill.categoryName}}</span>
                <span class="modal-meta-item">Lv.${{currentSkill.level}}</span>
                <span class="modal-meta-item">${{currentSkill.uses}} uses</span>
                <span class="modal-meta-item">${{'★'.repeat(currentSkill.stars)}}${{'☆'.repeat(5 - currentSkill.stars)}}</span>
            `;
            document.getElementById('modal-desc').textContent = currentSkill.description || 'No description available.';

            let bodyHtml = '';

            // Use Cases
            if (currentSkill.useCases && currentSkill.useCases.length > 0) {{
                bodyHtml += `<div class="modal-section">
                    <div class="modal-section-title">📋 Use Cases</div>
                    ${{currentSkill.useCases.map(uc => `
                        <div class="use-case">
                            <div class="use-case-title">${{uc.title}}</div>
                            <div class="use-case-item"><strong>Input:</strong> ${{uc.input}}</div>
                            <div class="use-case-item"><strong>Action:</strong> ${{uc.action}}</div>
                            <div class="use-case-item"><strong>Output:</strong> ${{uc.output}}</div>
                        </div>
                    `).join('')}}
                </div>`;
            }}

            // Triggers
            if (currentSkill.triggers && currentSkill.triggers.length > 0) {{
                bodyHtml += `<div class="modal-section">
                    <div class="modal-section-title">🎯 Trigger Keywords</div>
                    <div class="tag-list">
                        ${{currentSkill.triggers.map(t => `<span class="tag">"${{t}}"</span>`).join('')}}
                    </div>
                </div>`;
            }}

            // Don't Use When
            if (currentSkill.dontUse && currentSkill.dontUse.length > 0) {{
                bodyHtml += `<div class="modal-section">
                    <div class="modal-section-title">🚫 Don't Use When</div>
                    <div class="tag-list">
                        ${{currentSkill.dontUse.map(d => `<span class="tag danger">${{d}}</span>`).join('')}}
                    </div>
                </div>`;
            }}

            // Stats
            bodyHtml += `<div class="modal-section">
                <div class="modal-section-title">📊 Stats</div>
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem;">
                    <div style="background: var(--bg-card); padding: 0.75rem; border-radius: 0.5rem; text-align: center;">
                        <div style="font-size: 1.5rem; font-weight: bold; color: var(--gold);">${{currentSkill.uses}}</div>
                        <div style="font-size: 0.75rem; color: var(--text-secondary);">Total Uses</div>
                    </div>
                    <div style="background: var(--bg-card); padding: 0.75rem; border-radius: 0.5rem; text-align: center;">
                        <div style="font-size: 1.5rem; font-weight: bold; color: var(--accent);">Lv.${{currentSkill.level}}</div>
                        <div style="font-size: 0.75rem; color: var(--text-secondary);">Level</div>
                    </div>
                    <div style="background: var(--bg-card); padding: 0.75rem; border-radius: 0.5rem; text-align: center;">
                        <div style="font-size: 1.5rem; font-weight: bold;">${{currentSkill.lastUsed || '-'}}</div>
                        <div style="font-size: 0.75rem; color: var(--text-secondary);">Last Used</div>
                    </div>
                </div>
            </div>`;

            document.getElementById('modal-body').innerHTML = bodyHtml;
            document.getElementById('modal-overlay').classList.add('show');
        }}

        function closeModal() {{
            document.getElementById('modal-overlay').classList.remove('show');
            currentSkill = null;
        }}

        function copySkillCommand() {{
            if (currentSkill) {{
                navigator.clipboard.writeText('/' + currentSkill.name);
                alert('Copied: /' + currentSkill.name);
            }}
        }}

        // Close modal on outside click
        document.getElementById('modal-overlay').addEventListener('click', (e) => {{
            if (e.target.id === 'modal-overlay') closeModal();
        }});

        // Close modal on Escape
        document.addEventListener('keydown', (e) => {{
            if (e.key === 'Escape') closeModal();
        }});
    </script>
</body>
</html>
'''

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)

    return str(OUTPUT_FILE)

def main():
    output_path = generate_dashboard()
    print(f"Dashboard: {output_path}")

    if '--open' in sys.argv or len(sys.argv) == 1:
        subprocess.run(['open', output_path])

if __name__ == "__main__":
    main()
