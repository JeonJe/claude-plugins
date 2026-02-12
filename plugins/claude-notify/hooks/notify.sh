#!/bin/bash
MESSAGE="$1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/notify-config.sh"

PROJECT=$(basename "$PWD" 2>/dev/null || echo '')
PANE_ID="none"
SESSION_TARGET="none"

if [ "$USE_TMUX" = "true" ] && [ -n "$TMUX_PANE" ]; then
    PANE_ID="$TMUX_PANE"
    SESSION_TARGET=$("$TMUX_PATH" display-message -t "$TMUX_PANE" -p '#S:#I' 2>/dev/null || echo 'none')
fi

# Escape single quotes to prevent Lua injection
MSG_SAFE="${MESSAGE//\'/\'\\\'\'}"
ST_SAFE="${SESSION_TARGET//\'/\'\\\'\'}"
PI_SAFE="${PANE_ID//\'/\'\\\'\'}"
PJ_SAFE="${PROJECT//\'/\'\\\'\'}"

"$HS_PATH" -c "ClaudeNotify.push('${MSG_SAFE}', '${ST_SAFE}', '${PI_SAFE}', '${PJ_SAFE}')"
