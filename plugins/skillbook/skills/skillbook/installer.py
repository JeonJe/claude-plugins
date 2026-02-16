#!/usr/bin/env python3
"""
Skillbook Installer - Automated install/uninstall/status for Skillbook.

Handles:
  - Copying skill files to ~/.claude/skills/skillbook/
  - Copying hook file to ~/.claude/hooks/
  - Merging hook entry into ~/.claude/settings.json (with backup)
  - Creating default config at ~/.claude/skillbook.config.json
  - Verifying installation health
  - Clean uninstall (with optional --purge)

Usage:
  python3 installer.py install
  python3 installer.py uninstall [--purge]
  python3 installer.py status
"""

import json
import os
import shutil
import stat
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HOME = Path.home()
CLAUDE_DIR = HOME / ".claude"
SETTINGS_FILE = CLAUDE_DIR / "settings.json"
CONFIG_FILE = CLAUDE_DIR / "skillbook.config.json"

SKILL_INSTALL_DIR = CLAUDE_DIR / "skills" / "skillbook"
HOOKS_DIR = CLAUDE_DIR / "hooks"

HOOK_FILENAME = "skill-usage-tracker.py"
HOOK_INSTALL_PATH = HOOKS_DIR / HOOK_FILENAME
HOOK_COMMAND = "python3 ~/.claude/hooks/skill-usage-tracker.py"

# Patterns that identify a skillbook hook in settings.json
HOOK_DETECT_PATTERNS = ("skill-usage-tracker", "command-usage-tracker")

# Files/dirs to skip when copying skill files
SKIP_PATTERNS = {"__pycache__", ".pyc"}

DEFAULT_CONFIG = {
    "statsFile": "~/.claude/skillbook-stats.json",
    "outputDir": "~/.claude/skillbook",
    "language": "en",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_ok(msg):
    print(f"  [OK] {msg}")


def _print_fail(msg):
    print(f"  [!!] {msg}")


def _print_skip(msg):
    print(f"  [--] {msg}")


def _print_info(msg):
    print(f"  ... {msg}")


def _timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _should_skip(name):
    """Return True if file/directory name should be skipped during copy."""
    return name in SKIP_PATTERNS or name.endswith(".pyc")


def _validate_stats_path(path_str):
    """Validate that stats path is within safe boundaries.

    Args:
        path_str: Path string to validate

    Returns:
        Path: Validated and resolved path

    Raises:
        ValueError: If path is outside current user's home directory
    """
    path = Path(path_str).expanduser().resolve()
    home_dir = HOME.resolve()

    try:
        path.relative_to(home_dir)
    except ValueError:
        raise ValueError(
            f"Stats file must be within {home_dir}.\n"
            f"         Got: {path}"
        )

    return path


def _resolve_source_dir():
    """Return the skill source directory (where this installer.py lives).

    Raises:
        RuntimeError: If the source directory is a symbolic link.
    """
    source = Path(__file__)

    # Check for symbolic link attack
    if source.is_symlink():
        raise RuntimeError(
            f"Security: installer.py is a symbolic link.\n"
            f"         This may indicate a malicious setup."
        )

    return source.resolve().parent


def _resolve_hook_source():
    """Return the path to the hook file in the repo.

    Looks for the Python hook first, then falls back to .sh.
    The repo structure is:
      plugins/skillbook/hooks/skill-usage-tracker.py (or .sh)
      plugins/skillbook/skills/skillbook/installer.py  <-- this file
    """
    repo_hooks_dir = _resolve_source_dir().parent.parent / "hooks"
    py_hook = repo_hooks_dir / "skill-usage-tracker.py"
    sh_hook = repo_hooks_dir / "skill-usage-tracker.sh"

    if py_hook.exists():
        return py_hook
    if sh_hook.exists():
        return sh_hook
    return None


def _read_settings():
    """Read and parse settings.json. Returns (dict, error_msg).

    On success: (settings_dict, None)
    On file-not-found: ({}, None)
    On parse error: (None, error_message)
    """
    if not SETTINGS_FILE.exists():
        return {}, None

    try:
        text = SETTINGS_FILE.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"Cannot read {SETTINGS_FILE}: {exc}"

    if not text.strip():
        return {}, None

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, (
            f"Malformed JSON in {SETTINGS_FILE} (line {exc.lineno}).\n"
            f"  Fix the file manually, then retry installation."
        )
    return data, None


def _write_settings(data):
    """Write settings dict to settings.json with validation round-trip."""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    SETTINGS_FILE.write_text(text, encoding="utf-8")

    # Validate by re-reading
    reloaded = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    if reloaded != data:
        raise RuntimeError("settings.json validation failed after write")


def _backup_settings():
    """Create a timestamped backup of settings.json. Returns backup path or None."""
    if not SETTINGS_FILE.exists():
        return None
    backup = SETTINGS_FILE.with_name(f"settings.json.bak.{_timestamp()}")
    shutil.copy2(SETTINGS_FILE, backup)
    return backup


def _find_hook_indices(settings):
    """Find indices of existing skillbook hooks in UserPromptSubmit array.

    Returns list of (index, command_string) tuples.
    """
    hooks_section = settings.get("hooks", {})
    user_prompt_hooks = hooks_section.get("UserPromptSubmit", [])
    matches = []

    for i, entry in enumerate(user_prompt_hooks):
        for hook in entry.get("hooks", []):
            cmd = hook.get("command", "")
            if any(pattern in cmd for pattern in HOOK_DETECT_PATTERNS):
                matches.append((i, cmd))
                break
    return matches


# ---------------------------------------------------------------------------
# Core Functions
# ---------------------------------------------------------------------------

def check_python_version():
    """Verify Python 3.8+ is available.

    Returns:
        True if version is sufficient, False otherwise.
    """
    major, minor = sys.version_info[:2]
    version_str = f"{major}.{minor}.{sys.version_info[2]}"

    if (major, minor) >= (3, 8):
        _print_ok(f"Python {version_str}")
        return True

    _print_fail(
        f"Python 3.8+ required. You have Python {version_str}.\n"
        f"         Please upgrade: https://www.python.org/downloads/"
    )
    return False


def detect_existing_install():
    """Detect current installation state.

    Returns:
        dict with keys: skill_files, hook_file, hook_registered, config_exists
    """
    result = {
        "skill_files": SKILL_INSTALL_DIR.exists()
            and (SKILL_INSTALL_DIR / "skillbook.py").exists(),
        "hook_file": HOOK_INSTALL_PATH.exists(),
        "hook_registered": False,
        "config_exists": CONFIG_FILE.exists(),
    }

    settings, err = _read_settings()
    if settings is not None:
        result["hook_registered"] = len(_find_hook_indices(settings)) > 0

    return result


def copy_skill_files():
    """Copy skill files from the repo to ~/.claude/skills/skillbook/.

    Creates a timestamped backup if skill files already exist.

    Returns:
        True on success, False on failure.
    """
    source_dir = _resolve_source_dir()
    if not source_dir.exists():
        _print_fail(f"Source directory not found: {source_dir}")
        return False

    try:
        SKILL_INSTALL_DIR.parent.mkdir(parents=True, exist_ok=True)

        # Backup existing installation
        if SKILL_INSTALL_DIR.exists() and (SKILL_INSTALL_DIR / "skillbook.py").exists():
            backup_dir = SKILL_INSTALL_DIR.with_name(f"skillbook.bak.{_timestamp()}")
            shutil.copytree(SKILL_INSTALL_DIR, backup_dir)
            _print_info(f"Backup: {backup_dir}")

        shutil.copytree(
            source_dir,
            SKILL_INSTALL_DIR,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            dirs_exist_ok=True,
        )
        _print_ok(f"Skill files      {SKILL_INSTALL_DIR}/")
        return True
    except OSError as exc:
        _print_fail(f"Failed to copy skill files: {exc}")
        return False


def copy_hook_file():
    """Copy the hook file to ~/.claude/hooks/ and set executable.

    Returns:
        True on success, False on failure.
    """
    source_hook = _resolve_hook_source()
    if source_hook is None:
        _print_fail(
            "Hook file not found in repo. Expected at:\n"
            f"         {_resolve_source_dir().parent.parent / 'hooks' / 'skill-usage-tracker.py'}"
        )
        return False

    try:
        HOOKS_DIR.mkdir(parents=True, exist_ok=True)

        # Determine destination filename based on source extension
        dest_name = f"skill-usage-tracker{source_hook.suffix}"
        dest_path = HOOKS_DIR / dest_name

        shutil.copy2(source_hook, dest_path)

        # Set executable permission (owner only)
        dest_path.chmod(0o755)

        _print_ok(f"Hook file        {dest_path}")
        return True
    except OSError as exc:
        _print_fail(f"Failed to copy hook file: {exc}")
        return False


def merge_settings_json():
    """Merge the skillbook hook into settings.json with backup.

    Steps:
      1. Backup existing settings.json
      2. Read current settings (handle missing/empty)
      3. Check for duplicate hook (pattern-based)
      4. Append or update hook entry
      5. Write with validation

    Returns:
        True on success, False on failure.
    """
    # Read current settings
    settings, err = _read_settings()
    if settings is None:
        _print_fail(err)
        return False

    # Detect existing hooks
    existing = _find_hook_indices(settings)

    # Determine the correct command based on what hook file we have
    source_hook = _resolve_hook_source()
    if source_hook is not None and source_hook.suffix == ".sh":
        hook_command = f"bash ~/.claude/hooks/skill-usage-tracker.sh"
    else:
        hook_command = HOOK_COMMAND

    # Check if hook is already registered with the correct command
    for _idx, cmd in existing:
        if cmd == hook_command:
            _print_skip("Hook already registered in settings.json")
            return True

    # Backup before modification
    backup_path = _backup_settings()
    if backup_path:
        _print_info(f"Backup: {backup_path}")

    # Build the new hook entry
    new_hook_entry = {
        "hooks": [
            {
                "type": "command",
                "command": hook_command,
            }
        ]
    }

    # If there are old skillbook hooks with a different command, update them
    if existing:
        hooks_section = settings.get("hooks", {})
        old_hooks = hooks_section.get("UserPromptSubmit", [])
        update_indices = {idx for idx, _ in existing}

        user_prompt_hooks = [
            new_hook_entry if i in update_indices else entry
            for i, entry in enumerate(old_hooks)
        ]

        settings = {**settings, "hooks": {**hooks_section, "UserPromptSubmit": user_prompt_hooks}}
        _print_ok(f"Hook updated     settings.json (UserPromptSubmit)")
    else:
        # Append new hook
        hooks_section = settings.get("hooks", {})
        user_prompt_hooks = list(hooks_section.get("UserPromptSubmit", []))
        user_prompt_hooks.append(new_hook_entry)

        settings = {
            **settings,
            "hooks": {**hooks_section, "UserPromptSubmit": user_prompt_hooks},
        }
        _print_ok(f"Hook registered  settings.json (UserPromptSubmit)")

    # Write and validate
    try:
        _write_settings(settings)
        return True
    except (OSError, RuntimeError) as exc:
        _print_fail(f"Failed to write settings.json: {exc}")
        return False


def create_default_config():
    """Create default config file if it does not exist.

    Returns:
        True always (config creation is optional).
    """
    if CONFIG_FILE.exists():
        _print_skip("Config already exists, keeping your settings")
        return True

    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False) + "\n"
        CONFIG_FILE.write_text(text, encoding="utf-8")
        _print_ok(f"Config           {CONFIG_FILE}")
        return True
    except OSError as exc:
        _print_fail(f"Failed to create config: {exc}")
        return True  # Non-fatal


def verify_installation():
    """Verify all installation components and print a status table.

    Returns:
        True if all checks pass, False if any fail.
    """
    print("\n  Skillbook Installation Status")
    print("  " + "=" * 40)

    all_ok = True

    # 1. Skill files
    skill_main = SKILL_INSTALL_DIR / "skillbook.py"
    if skill_main.exists():
        _print_ok(f"Skill files      {SKILL_INSTALL_DIR}/")
    else:
        _print_fail(f"Skill files      {SKILL_INSTALL_DIR}/ (missing)")
        all_ok = False

    # 2. Hook file
    hook_found = False
    for ext in (".py", ".sh"):
        hook_path = HOOKS_DIR / f"skill-usage-tracker{ext}"
        if hook_path.exists():
            is_exec = os.access(hook_path, os.X_OK)
            if is_exec:
                _print_ok(f"Hook file        {hook_path}")
            else:
                _print_fail(f"Hook file        {hook_path} (not executable)")
                all_ok = False
            hook_found = True
            break
    if not hook_found:
        _print_fail(f"Hook file        {HOOKS_DIR}/skill-usage-tracker.py (missing)")
        all_ok = False

    # 3. Hook registered in settings.json
    settings, err = _read_settings()
    if settings is None:
        _print_fail(f"settings.json    {err}")
        all_ok = False
    else:
        hooks = _find_hook_indices(settings)
        if hooks:
            _print_ok("Hook registered  settings.json (UserPromptSubmit)")
        else:
            _print_fail("Hook registered  Not found in settings.json")
            all_ok = False

    # 4. Config file
    if CONFIG_FILE.exists():
        _print_ok(f"Config           {CONFIG_FILE}")
    else:
        _print_skip(f"Config           {CONFIG_FILE} (optional, not created)")

    # 5. Python version
    major, minor, micro = sys.version_info[:3]
    if (major, minor) >= (3, 8):
        _print_ok(f"Python 3.8+      Python {major}.{minor}.{micro}")
    else:
        _print_fail(f"Python 3.8+      Python {major}.{minor}.{micro} (too old)")
        all_ok = False

    return all_ok


# ---------------------------------------------------------------------------
# Orchestrators
# ---------------------------------------------------------------------------

def install():
    """Run the full installation sequence.

    Steps:
      1. Check Python version
      2. Copy skill files
      3. Copy hook file
      4. Merge settings.json
      5. Create default config
      6. Verify installation
    """
    print("\n  Skillbook Installer")
    print("  " + "=" * 40)

    # Step 1: Python version gate
    if not check_python_version():
        print("\n  Installation aborted.")
        sys.exit(1)

    # Step 2: Copy skill files
    if not copy_skill_files():
        print("\n  Installation failed at: copy skill files")
        sys.exit(1)

    # Step 3: Copy hook file
    if not copy_hook_file():
        print("\n  Installation failed at: copy hook file")
        sys.exit(1)

    # Step 4: Merge settings.json
    if not merge_settings_json():
        print("\n  Installation failed at: merge settings.json")
        sys.exit(1)

    # Step 5: Create default config (non-fatal)
    create_default_config()

    # Step 6: Verify
    ok = verify_installation()
    if ok:
        print("\n  Installation complete! Try: /skillbook")
    else:
        print("\n  Installation finished with warnings. Check above for details.")

    print()


def uninstall(purge=False):
    """Remove skillbook hooks and optionally skill files.

    With purge=False (default):
      - Remove hook entry from settings.json
      - Remove hook file from ~/.claude/hooks/
      - Skill files are kept

    With purge=True:
      - All of the above
      - Remove ~/.claude/skills/skillbook/ directory
      - Remove ~/.claude/skillbook.config.json
      - Stats file is NEVER deleted

    Args:
        purge: If True, remove skill files and config too.
    """
    print("\n  Skillbook Uninstaller")
    print("  " + "=" * 40)

    removed = []

    # 1. Remove hook from settings.json
    settings, err = _read_settings()
    if settings is None:
        _print_fail(f"Cannot read settings.json: {err}")
        _print_info("Skipping settings.json modification")
    elif settings:
        existing = _find_hook_indices(settings)
        if existing:
            backup_path = _backup_settings()
            if backup_path:
                _print_info(f"Backup: {backup_path}")

            hooks_section = settings.get("hooks", {})
            user_prompt_hooks = list(hooks_section.get("UserPromptSubmit", []))

            # Remove in reverse order to preserve indices
            for idx, cmd in sorted(existing, key=lambda x: x[0], reverse=True):
                user_prompt_hooks.pop(idx)
                removed.append(f"Hook entry: {cmd}")

            # Clean up empty structures
            if user_prompt_hooks:
                updated_hooks = {**hooks_section, "UserPromptSubmit": user_prompt_hooks}
            else:
                updated_hooks = {
                    k: v for k, v in hooks_section.items()
                    if k != "UserPromptSubmit"
                }

            if updated_hooks:
                updated_settings = {**settings, "hooks": updated_hooks}
            else:
                updated_settings = {k: v for k, v in settings.items() if k != "hooks"}

            try:
                _write_settings(updated_settings)
                _print_ok("Hook removed from settings.json")
            except (OSError, RuntimeError) as exc:
                _print_fail(f"Failed to update settings.json: {exc}")
        else:
            _print_skip("No skillbook hook found in settings.json")

    # 2. Remove hook file(s)
    for ext in (".py", ".sh"):
        hook_path = HOOKS_DIR / f"skill-usage-tracker{ext}"
        if hook_path.exists():
            try:
                hook_path.unlink()
                removed.append(f"Hook file: {hook_path}")
                _print_ok(f"Removed {hook_path}")
            except OSError as exc:
                _print_fail(f"Failed to remove {hook_path}: {exc}")

    # 3. Purge: remove skill files and config
    if purge:
        if SKILL_INSTALL_DIR.exists():
            try:
                shutil.rmtree(SKILL_INSTALL_DIR)
                removed.append(f"Skill directory: {SKILL_INSTALL_DIR}")
                _print_ok(f"Removed {SKILL_INSTALL_DIR}/")
            except OSError as exc:
                _print_fail(f"Failed to remove skill directory: {exc}")

        if CONFIG_FILE.exists():
            try:
                CONFIG_FILE.unlink()
                removed.append(f"Config: {CONFIG_FILE}")
                _print_ok(f"Removed {CONFIG_FILE}")
            except OSError as exc:
                _print_fail(f"Failed to remove config: {exc}")

        # Explicit reminder: stats are preserved
        stats_path = _find_stats_path()
        if stats_path.exists():
            _print_info(f"Stats file preserved at {stats_path}")
    else:
        _print_skip("Skill files kept (use --purge to remove)")

    # Summary
    if removed:
        print(f"\n  Removed {len(removed)} component(s).")
    else:
        print("\n  Nothing to remove. Skillbook was not installed.")

    print()


def _find_stats_path():
    """Find the stats file path from config or default."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                cfg = json.load(f)
            if "statsFile" in cfg:
                return _validate_stats_path(cfg["statsFile"])
        except (OSError, json.JSONDecodeError, ValueError):
            pass
    return CLAUDE_DIR / "skillbook-stats.json"


def status():
    """Show current installation state without modifying anything."""
    print()
    ok = verify_installation()

    # Additional info: stats
    stats_path = _find_stats_path()
    if stats_path.exists():
        try:
            with open(stats_path, encoding="utf-8") as f:
                data = json.load(f)
            total = data.get("totalUses", 0)
            skill_count = len(data.get("skills", {}))
            _print_info(f"Stats: {skill_count} skills tracked, {total} total uses")
        except (OSError, json.JSONDecodeError):
            _print_info(f"Stats file exists but could not be read: {stats_path}")
    else:
        _print_info("No stats file found (will be created on first skill use)")

    if ok:
        print("\n  All components installed correctly.")
    else:
        print("\n  Some components are missing. Run: /skillbook install")

    print()


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main():
    """CLI entrypoint for standalone usage."""
    args = sys.argv[1:]

    if not args:
        print("Usage: python3 installer.py [install|uninstall|status]")
        print("  install             Install skillbook (hooks, config, files)")
        print("  uninstall           Remove hooks (keep skill files)")
        print("  uninstall --purge   Remove hooks + skill files (keep stats)")
        print("  status              Show installation health")
        sys.exit(0)

    command = args[0].lower()

    if command == "install":
        install()
    elif command == "uninstall":
        purge = "--purge" in args
        uninstall(purge=purge)
    elif command == "status":
        status()
    else:
        print(f"Unknown command: {command}")
        print("Usage: python3 installer.py [install|uninstall|status]")
        sys.exit(1)


if __name__ == "__main__":
    main()
