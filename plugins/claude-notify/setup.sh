#!/bin/bash
set -e

# ─── Claude Notify Setup ───────────────────────────────────────────
# Interactive setup for Claude Code notification panel (Hammerspoon)
# Detects environment, prompts for choices, generates config files.
# ────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_LUA="$HOME/.hammerspoon/claude-notify-config.lua"
CONFIG_SH="$HOME/.claude/hooks/notify-config.sh"
NOTIFY_HOOK="$HOME/.claude/hooks/notify.sh"
NOTIFY_LUA="$HOME/.hammerspoon/claude-notify.lua"

echo "╔══════════════════════════════════════╗"
echo "║   Claude Code Notify - Setup         ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ─── 1. Hammerspoon ────────────────────────────────────────────────
echo "▶ [1/6] Checking Hammerspoon..."

HS_PATH=""
if command -v hs &>/dev/null; then
    HS_PATH=$(command -v hs)
    echo "  ✓ hs CLI found: $HS_PATH"
elif [ -f /opt/homebrew/bin/hs ]; then
    HS_PATH="/opt/homebrew/bin/hs"
    echo "  ✓ hs CLI found: $HS_PATH"
elif [ -f /usr/local/bin/hs ]; then
    HS_PATH="/usr/local/bin/hs"
    echo "  ✓ hs CLI found: $HS_PATH"
else
    echo "  ✗ Hammerspoon CLI (hs) not found."
    echo ""
    echo "  Install Hammerspoon: https://www.hammerspoon.org/"
    echo "  Then enable CLI: Hammerspoon Preferences > Enable CLI"
    echo "  Or run in Hammerspoon console: hs.ipc.cliInstall()"
    exit 1
fi

# ─── 2. Terminal App ───────────────────────────────────────────────
echo ""
echo "▶ [2/6] Detecting terminal app..."

DETECTED_TERMINAL=""
if [ -n "$TERM_PROGRAM" ]; then
    case "$TERM_PROGRAM" in
        ghostty) DETECTED_TERMINAL="Ghostty" ;;
        iTerm.app) DETECTED_TERMINAL="iTerm2" ;;
        Apple_Terminal) DETECTED_TERMINAL="Terminal" ;;
        WezTerm) DETECTED_TERMINAL="WezTerm" ;;
        *) DETECTED_TERMINAL="$TERM_PROGRAM" ;;
    esac
fi

TERMINALS=("Ghostty" "iTerm2" "Terminal" "WezTerm" "Alacritty" "Other")
echo "  Detected: ${DETECTED_TERMINAL:-none}"
echo ""
echo "  Select your terminal:"
for i in "${!TERMINALS[@]}"; do
    marker=""
    if [ "${TERMINALS[$i]}" = "$DETECTED_TERMINAL" ]; then
        marker=" (detected)"
    fi
    echo "    $((i+1))) ${TERMINALS[$i]}${marker}"
done
echo ""
read -p "  Choice [1-${#TERMINALS[@]}]: " term_choice

if [ -z "$term_choice" ] && [ -n "$DETECTED_TERMINAL" ]; then
    TERMINAL="$DETECTED_TERMINAL"
else
    idx=$((term_choice - 1))
    if [ "$idx" -ge 0 ] && [ "$idx" -lt "${#TERMINALS[@]}" ]; then
        if [ "${TERMINALS[$idx]}" = "Other" ]; then
            read -p "  Enter terminal app name: " TERMINAL
        else
            TERMINAL="${TERMINALS[$idx]}"
        fi
    else
        TERMINAL="${DETECTED_TERMINAL:-Ghostty}"
    fi
fi
echo "  → Terminal: $TERMINAL"

# ─── 3. tmux ───────────────────────────────────────────────────────
echo ""
echo "▶ [3/6] Checking tmux..."

TMUX_PATH=""
USE_TMUX="false"

if command -v tmux &>/dev/null; then
    TMUX_PATH=$(command -v tmux)
    echo "  ✓ tmux found: $TMUX_PATH"
    echo ""
    read -p "  Use tmux session navigation? (Y/n): " tmux_answer
    if [ "$tmux_answer" != "n" ] && [ "$tmux_answer" != "N" ]; then
        USE_TMUX="true"
        echo "  → tmux navigation: enabled"
    else
        echo "  → tmux navigation: disabled"
    fi
else
    echo "  ✗ tmux not found (navigation will focus terminal app only)"
fi

# ─── 4. Language ───────────────────────────────────────────────────
echo ""
echo "▶ [4/6] Notification language"
echo "    1) English"
echo "    2) 한국어 (Korean)"
echo ""
read -p "  Choice [1-2]: " lang_choice

if [ "$lang_choice" = "2" ]; then
    LANG_CODE="ko"
    MSG_INPUT="🔔 Yo!"
    MSG_DONE="✅ Ta-da!"
    echo "  → Language: 한국어"
else
    LANG_CODE="en"
    MSG_INPUT="🔔 Yo!"
    MSG_DONE="✅ Ta-da!"
    echo "  → Language: English"
fi

# ─── 5. Hotkey ─────────────────────────────────────────────────────
echo ""
echo "▶ [5/6] Toggle hotkey"
echo "  Default: Ctrl+Shift+N"
read -p "  Use default? (Y/n): " hotkey_answer

if [ "$hotkey_answer" = "n" ] || [ "$hotkey_answer" = "N" ]; then
    echo "  Modifier options: ctrl, shift, alt, cmd"
    read -p "  Modifiers (comma-separated, e.g. ctrl,shift): " hotkey_mods_raw
    read -p "  Key (e.g. n, m, /): " hotkey_key
    HOTKEY_MODS="$hotkey_mods_raw"
    HOTKEY_KEY="$hotkey_key"
else
    HOTKEY_MODS="ctrl,shift"
    HOTKEY_KEY="n"
fi
echo "  → Hotkey: ${HOTKEY_MODS}+${HOTKEY_KEY}"

# ─── 6. Port ──────────────────────────────────────────────────────
echo ""
echo "▶ [6/6] HTTP callback port"
echo "  Default: 17839"
read -p "  Port [17839]: " port_input
PORT="${port_input:-17839}"
echo "  → Port: $PORT"

# ─── Copy Lua module ─────────────────────────────────────────────
echo ""
echo "━━━ Installing files... ━━━"

mkdir -p "$HOME/.hammerspoon"
cp "$SCRIPT_DIR/hammerspoon/claude-notify.lua" "$NOTIFY_LUA"
echo "  ✓ $NOTIFY_LUA"

# ─── Generate Lua config ──────────────────────────────────────────
LUA_MODS=""
IFS=',' read -ra MOD_ARRAY <<< "$HOTKEY_MODS"
for mod in "${MOD_ARRAY[@]}"; do
    mod=$(echo "$mod" | xargs) # trim
    LUA_MODS="${LUA_MODS}\"${mod}\", "
done
LUA_MODS="${LUA_MODS%, }"

cat > "$CONFIG_LUA" << LUAEOF
-- Claude Notify Config (generated by setup)
return {
    terminal = "${TERMINAL}",
    hs_path = "${HS_PATH}",
    tmux_path = "${TMUX_PATH}",
    use_tmux = ${USE_TMUX},
    port = ${PORT},
    hotkey_mods = { ${LUA_MODS} },
    hotkey_key = "${HOTKEY_KEY}",
    lang = "${LANG_CODE}",
    panel = {
        width = 320,
        height = 420,
        alpha = 0.93,
        always_on_top = true,
    },
}
LUAEOF
echo "  ✓ $CONFIG_LUA"

# ─── Generate Bash config ─────────────────────────────────────────
mkdir -p "$HOME/.claude/hooks"

cat > "$CONFIG_SH" << SHEOF
# Claude Notify Config (generated by setup)
HS_PATH="${HS_PATH}"
TMUX_PATH="${TMUX_PATH}"
USE_TMUX=${USE_TMUX}
SHEOF
echo "  ✓ $CONFIG_SH"

# ─── Copy notify.sh hook ─────────────────────────────────────────
cp "$SCRIPT_DIR/hooks/notify.sh" "$NOTIFY_HOOK"
chmod +x "$NOTIFY_HOOK"
echo "  ✓ $NOTIFY_HOOK"

# ─── Print Claude Code hook settings ──────────────────────────────
echo ""
echo "━━━ Claude Code Hook Settings ━━━"
echo ""
echo "Add to ~/.claude/settings.json under \"hooks\":"
echo ""
cat << JSONEOF
    "Notification": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/hooks/notify.sh '${MSG_INPUT}'"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/hooks/notify.sh '${MSG_DONE}'"
          }
        ]
      }
    ]
JSONEOF

# ─── Print init.lua snippet ──────────────────────────────────────
echo ""
echo "━━━ Hammerspoon init.lua ━━━"
echo ""
echo "Add these lines to ~/.hammerspoon/init.lua:"
echo ""
echo '  require("hs.ipc")'
echo '  ClaudeNotify = require("claude-notify")'
echo '  ClaudeNotify.show()'

echo ""
echo "━━━ Setup Complete ━━━"
echo ""
echo "Next steps:"
echo "  1. Copy the hook settings above to ~/.claude/settings.json"
echo "  2. Add the init.lua lines to ~/.hammerspoon/init.lua"
echo "  3. Reload Hammerspoon (menu bar icon > Reload Config)"
echo ""
