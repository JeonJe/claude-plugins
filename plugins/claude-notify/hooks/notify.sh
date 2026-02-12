#!/bin/bash
HOOK_TYPE="$1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/notify-config.sh"

# Read hook context JSON from stdin (Claude Code pipes it)
read -t 1 CONTEXT 2>/dev/null || CONTEXT='{}'

PROJECT=$(basename "$PWD" 2>/dev/null || echo '')
PANE_ID="none"
SESSION_TARGET="none"

if [ "$USE_TMUX" = "true" ] && [ -n "$TMUX_PANE" ]; then
    PANE_ID="$TMUX_PANE"
    SESSION_TARGET=$("$TMUX_PATH" display-message -t "$TMUX_PANE" -p '#S:#I' 2>/dev/null || echo 'none')
fi

# Generate contextual message via python3
MESSAGE=$(echo "$CONTEXT" | HOOK_TYPE="$HOOK_TYPE" python3 -c '
import json, sys, os

hook_type = os.environ.get("HOOK_TYPE", "")
try:
    ctx = json.load(sys.stdin)
except:
    ctx = {}

event = ctx.get("hook_event_name", "")
notif_type = ctx.get("notification_type", "")
message = ctx.get("message", "")

if event == "Notification":
    if notif_type == "permission_prompt":
        if message:
            msg = message
            msg = msg.replace("Claude needs your permission to use ", "")
            msg = msg.replace("Claude wants to ", "")
            msg = msg.replace("Claude is requesting to ", "")
            if len(msg) > 55:
                msg = msg[:55] + "..."
            print(f"\U0001f514 {msg}")
        else:
            print("\U0001f514 Approval needed")
    elif notif_type == "idle_prompt":
        print("\U0001f514 Waiting for input")
    elif notif_type == "elicitation_dialog":
        print("\U0001f514 Question pending")
    elif notif_type == "auth_success":
        print("\u2705 Auth complete")
    else:
        if message:
            short = message[:55] + "..." if len(message) > 55 else message
            print(f"\U0001f514 {short}")
        else:
            print("\U0001f514 Attention needed")
elif event == "Stop":
    print("\u2705 Task completed")
else:
    # Legacy fallback: $1 is the raw message
    if hook_type and hook_type not in ("notification", "stop"):
        print(hook_type)
    elif hook_type == "stop":
        print("\u2705 Task completed")
    else:
        print("\U0001f514 Notification")
' 2>/dev/null)

# Fallback if python3 fails
if [ -z "$MESSAGE" ]; then
    case "$HOOK_TYPE" in
        notification) MESSAGE="🔔 Attention needed" ;;
        stop)         MESSAGE="✅ Task completed" ;;
        *)            MESSAGE="${HOOK_TYPE:-Notification}" ;;
    esac
fi

# Escape single quotes to prevent Lua injection
MSG_SAFE="${MESSAGE//\'/\'\\\'\'}"
ST_SAFE="${SESSION_TARGET//\'/\'\\\'\'}"
PI_SAFE="${PANE_ID//\'/\'\\\'\'}"
PJ_SAFE="${PROJECT//\'/\'\\\'\'}"

"$HS_PATH" -c "ClaudeNotify.push('${MSG_SAFE}', '${ST_SAFE}', '${PI_SAFE}', '${PJ_SAFE}')"
