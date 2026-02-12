local ClaudeNotify = {}

-- ─── Load config ──────────────────────────────────────────────────
local ok, userConfig = pcall(require, "claude-notify-config")
if not ok then
    userConfig = {}
end

local defaults = {
    terminal = "Ghostty",
    hs_path = "/opt/homebrew/bin/hs",
    tmux_path = "/opt/homebrew/bin/tmux",
    use_tmux = true,
    port = 17839,
    hotkey_mods = { "ctrl", "shift" },
    hotkey_key = "n",
    lang = "en",
    theme = "dark",
    panel = {
        width = 320,
        height = 420,
        alpha = 0.93,
        always_on_top = true,
    },
}

-- Merge user config over defaults
local cfg = {}
for k, v in pairs(defaults) do
    if type(v) == "table" and type(userConfig[k]) == "table" then
        cfg[k] = {}
        for sk, sv in pairs(v) do
            cfg[k][sk] = userConfig[k][sk] ~= nil and userConfig[k][sk] or sv
        end
    else
        cfg[k] = userConfig[k] ~= nil and userConfig[k] or v
    end
end

-- ─── State ────────────────────────────────────────────────────────
local webview = nil
local notifications = {}
local nextId = 1
local MAX_NOTIFICATIONS = 30
local isVisible = false
local callbackServer = nil

local panelState = {
    alpha = cfg.panel.alpha,
    filter = "all",
    fontSize = 13,
    theme = cfg.theme,
}

local toastView = nil
local toastTimer = nil
local TOAST_DURATION = 4

-- ─── HTTP callback server ─────────────────────────────────────────
callbackServer = hs.httpserver.new(false, false)
callbackServer:setPort(cfg.port)
callbackServer:setCallback(function(_, path)
    if path:match("^/clear") then
        ClaudeNotify.clear()
    elseif path:match("^/alpha/") then
        local val = tonumber(path:match("^/alpha/([%d%.]+)"))
        if val then
            ClaudeNotify.setAlpha(val)
        end
    elseif path:match("^/click/") then
        local id = tonumber(path:match("^/click/([%d]+)"))
        if id then
            ClaudeNotify.onClickNotification(id)
        end
    elseif path:match("^/readall") then
        ClaudeNotify.markAllRead()
    elseif path:match("^/fontsize/") then
        local val = tonumber(path:match("^/fontsize/([%d]+)"))
        if val then
            panelState.fontSize = val
            ClaudeNotify.updatePanel()
        end
    elseif path:match("^/filter/") then
        local mode = path:match("^/filter/(%a+)")
        if mode then
            ClaudeNotify.setFilter(mode)
        end
    elseif path:match("^/theme/") then
        local mode = path:match("^/theme/(%a+)")
        if mode then
            ClaudeNotify.setTheme(mode)
        end
    elseif path:match("^/quit") then
        ClaudeNotify.quit()
    elseif path:match("^/restart") then
        ClaudeNotify.restart()
    end
    return "ok", 200, {}
end)
callbackServer:start()

-- ─── Helpers ─────────────────────────────────────────────────────
local function escapeHtml(text)
    if not text then return "" end
    return text:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;"):gsub('"', "&quot;"):gsub("'", "&#39;")
end

local function isValidTmuxId(id)
    if not id or id == "none" then return false end
    return id:match("^[%w_:%%.-]+$") ~= nil
end

-- ─── Core functions ───────────────────────────────────────────────
function ClaudeNotify.push(message, sessionTarget, paneId, project)
    local entry = {
        id = nextId,
        time = os.date("%H:%M:%S"),
        message = message,
        sessionTarget = sessionTarget or "none",
        paneId = paneId or "none",
        project = project or "",
        read = false,
    }
    nextId = nextId + 1
    table.insert(notifications, entry)
    if #notifications > MAX_NOTIFICATIONS then
        table.remove(notifications, 1)
    end
    ClaudeNotify.showToast(entry)
    if not isVisible then
        ClaudeNotify.show()
    else
        ClaudeNotify.updatePanel()
    end
end

function ClaudeNotify.focusPane(n)
    hs.application.launchOrFocus(cfg.terminal)
    if cfg.use_tmux and isValidTmuxId(n.sessionTarget) then
        local session = n.sessionTarget:match("^([^:]+)")
        if not session or not session:match("^[%w_.-]+$") then return end
        hs.timer.doAfter(0.3, function()
            hs.execute(cfg.tmux_path .. " switch-client -t " .. session .. " 2>/dev/null", true)
            hs.execute(cfg.tmux_path .. " select-window -t " .. n.sessionTarget .. " 2>/dev/null", true)
            if isValidTmuxId(n.paneId) then
                hs.execute(cfg.tmux_path .. " select-pane -t " .. n.paneId .. " 2>/dev/null", true)
            end
        end)
    end
end

function ClaudeNotify.onClickNotification(id)
    for _, n in ipairs(notifications) do
        if n.id == id then
            n.read = true
            ClaudeNotify.focusPane(n)
            break
        end
    end
    ClaudeNotify.hideToast()
    ClaudeNotify.updatePanel()
end

function ClaudeNotify.markAllRead()
    for _, n in ipairs(notifications) do
        n.read = true
    end
    ClaudeNotify.updatePanel()
end

function ClaudeNotify.setAlpha(value)
    if value < 0.1 then value = 0.1 end
    panelState.alpha = value
    if webview then
        webview:alpha(value)
    end
end

function ClaudeNotify.setFilter(mode)
    panelState.filter = mode
    ClaudeNotify.updatePanel()
end

function ClaudeNotify.setTheme(mode)
    if mode == "dark" or mode == "light" then
        panelState.theme = mode
        ClaudeNotify.updatePanel()
    end
end

function ClaudeNotify.hideToast()
    if toastTimer then
        toastTimer:stop()
        toastTimer = nil
    end
    if toastView then
        toastView:hide()
        toastView:delete()
        toastView = nil
    end
end

function ClaudeNotify.showToast(entry)
    ClaudeNotify.hideToast()

    local screen = hs.screen.mainScreen()
    local frame = screen:frame()
    local w = 380
    local h = 76
    local x = frame.x + (frame.w - w) / 2
    local y = frame.y + 6

    toastView = hs.webview.new(hs.geometry.rect(x, y, w, h))
        :windowStyle({"nonactivating"})
        :level(hs.drawing.windowLevels.overlay)
        :alpha(0.97)
        :allowTextEntry(false)
        :transparent(true)
        :deleteOnClose(false)

    local icon, iconClass = "--", "other"
    local displayMsg = entry.message
    if entry.message:find("\xF0\x9F\x94\x94") then
        icon, iconClass = "IN", "input"
        displayMsg = displayMsg:gsub("\xF0\x9F\x94\x94%s*", "")
    elseif entry.message:find("\xE2\x9C\x85") then
        icon, iconClass = "OK", "done"
        displayMsg = displayMsg:gsub("\xE2\x9C\x85%s*", "")
    end

    local meta = entry.time
    if entry.project and entry.project ~= "" then
        meta = '<span class="project">' .. escapeHtml(entry.project) .. "</span> · " .. meta
    end

    local html = string.format([[
<!DOCTYPE html>
<html data-theme="%s"><head>
<style>
    :root {
        --bg-toast: #1e1e35; --border: #3a3a5a;
        --text-bright: #e8e8f8; --text-dim: #7a7a9a;
        --dot: #6a9aff;
        --dot-glow: rgba(106,154,255,0.67); --dot-glow-outer: rgba(106,154,255,0.27);
        --dot-pulse: rgba(138,176,255,0.8); --dot-pulse-outer: rgba(106,154,255,0.4);
        --icon-input-bg: #2a2a55; --icon-input-fg: #7eb0ff;
        --icon-done-bg: #1e3a2a;  --icon-done-fg: #6ecc8e;
        --icon-other-bg: #2a2a3a; --icon-other-fg: #777;
        --tag-fg: #e0a060;
        --shadow: rgba(0,0,0,0.4); --shadow-sm: rgba(0,0,0,0.15);
    }
    [data-theme="light"] {
        --bg-toast: #ffffff; --border: #d0d0de;
        --text-bright: #111122; --text-dim: #666680;
        --dot: #4477ff;
        --dot-glow: rgba(68,119,255,0.5); --dot-glow-outer: rgba(68,119,255,0.2);
        --dot-pulse: rgba(85,136,255,0.7); --dot-pulse-outer: rgba(68,119,255,0.35);
        --icon-input-bg: #ddeaff; --icon-input-fg: #2266cc;
        --icon-done-bg: #ddf5e6;  --icon-done-fg: #228844;
        --icon-other-bg: #ececf0; --icon-other-fg: #999;
        --tag-fg: #aa6600;
        --shadow: rgba(0,0,0,0.12); --shadow-sm: rgba(0,0,0,0.06);
    }
    * { margin:0; padding:0; box-sizing:border-box; }
    body {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
        font-size: 13px; background: transparent; overflow: hidden;
        -webkit-user-select: none;
    }
    .toast {
        background: var(--bg-toast);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 12px 16px;
        display: flex; align-items: center; gap: 10px;
        cursor: pointer;
        box-shadow: 0 8px 32px var(--shadow), 0 2px 8px var(--shadow-sm);
        animation: slideDown 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
        transition: filter 0.15s;
    }
    .toast:hover { filter: brightness(1.08); }
    .toast:active { filter: brightness(0.95); }
    @keyframes slideDown {
        from { transform: translateY(-130%%); opacity: 0; }
        to   { transform: translateY(0); opacity: 1; }
    }
    .dot {
        width: 9px; height: 9px;
        background: var(--dot); border-radius: 50%%;
        flex-shrink: 0;
        box-shadow: 0 0 6px var(--dot-glow), 0 0 14px var(--dot-glow-outer);
        animation: pulse 2s ease-in-out infinite;
    }
    @keyframes pulse {
        0%%, 100%% { box-shadow: 0 0 6px var(--dot-glow), 0 0 14px var(--dot-glow-outer); }
        50%% { box-shadow: 0 0 12px var(--dot-pulse), 0 0 24px var(--dot-pulse-outer); }
    }
    .icon {
        font-size: 10px; font-weight: 700;
        padding: 3px 7px; border-radius: 4px;
        font-family: "SF Mono", Menlo, monospace; flex-shrink: 0;
    }
    .icon.input { background: var(--icon-input-bg); color: var(--icon-input-fg); }
    .icon.done  { background: var(--icon-done-bg);  color: var(--icon-done-fg); }
    .icon.other { background: var(--icon-other-bg); color: var(--icon-other-fg); }
    .content { flex: 1; min-width: 0; }
    .msg {
        color: var(--text-bright); font-weight: 500; font-size: 13px;
        line-height: 1.3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .meta {
        color: var(--text-dim); font-size: 11px; margin-top: 2px;
        font-family: "SF Mono", Menlo, monospace;
    }
    .meta .project { color: var(--tag-fg); }
</style>
<script>
function hs(path) {
    var x = new XMLHttpRequest();
    x.open('GET', 'http://localhost:%d' + path + '?t=' + Date.now());
    x.send();
}
</script>
</head><body>
<div class="toast" onclick="hs('/click/%d')">
    <span class="dot"></span>
    <span class="icon %s">%s</span>
    <div class="content">
        <div class="msg">%s</div>
        <div class="meta">%s</div>
    </div>
</div>
</body></html>
    ]],
        panelState.theme,
        cfg.port,
        entry.id,
        iconClass,
        icon,
        escapeHtml(displayMsg),
        meta
    )

    toastView:html(html)
    toastView:show()

    toastTimer = hs.timer.doAfter(TOAST_DURATION, function()
        ClaudeNotify.hideToast()
    end)
end

function ClaudeNotify.quit()
    ClaudeNotify.hideToast()
    if webview then
        webview:hide()
        webview:delete()
        webview = nil
    end
    isVisible = false
    if callbackServer then
        callbackServer:stop()
    end
end

function ClaudeNotify.restart()
    if webview then
        webview:hide()
        webview:delete()
        webview = nil
    end
    isVisible = false
    ClaudeNotify.show()
end

-- ─── Panel ────────────────────────────────────────────────────────
function ClaudeNotify.createPanel()
    local screen = hs.screen.mainScreen()
    local frame = screen:frame()
    local rect = hs.geometry.rect(
        frame.x + frame.w - cfg.panel.width - 16,
        frame.y + 40,
        cfg.panel.width,
        cfg.panel.height
    )
    webview = hs.webview.new(rect)
        :windowStyle({ "utility", "nonactivating", "titled", "resizable", "closable", "miniaturizable" })
        :level(cfg.panel.always_on_top and hs.drawing.windowLevels.floating or hs.drawing.windowLevels.normal)
        :alpha(panelState.alpha)
        :allowTextEntry(true)
        :closeOnEscape(true)
        :windowTitle("Claude Notify")
        :deleteOnClose(false)

    return webview
end

function ClaudeNotify.generateHTML()
    local items = ""
    local unreadCount = 0
    for _, n in ipairs(notifications) do
        if not n.read then
            unreadCount = unreadCount + 1
        end
    end

    for i = #notifications, 1, -1 do
        local n = notifications[i]

        -- Filter
        if panelState.filter == "input" and not n.message:find("\xF0\x9F\x94\x94") then
            goto continue
        end
        if panelState.filter == "done" and not n.message:find("\xE2\x9C\x85") then
            goto continue
        end

        local isNew = (i == #notifications) and not n.read
        local idx = #notifications - i
        local readClass = n.read and " read" or " unread"
        local rowClass = (idx % 2 == 0) and "item even" or "item odd"
        rowClass = rowClass .. readClass
        if isNew then
            rowClass = rowClass .. " new"
        end

        -- Tags: project + session name (escaped)
        local tags = ""
        if n.project and n.project ~= "" then
            tags = tags .. string.format('<span class="tag project">%s</span>', escapeHtml(n.project))
        end
        if cfg.use_tmux and n.sessionTarget and n.sessionTarget ~= "none" then
            tags = tags .. string.format('<span class="tag session">%s</span>', escapeHtml(n.sessionTarget))
        end

        -- Icon: detect by emoji (language-independent)
        local icon = ""
        local displayMsg = n.message
        if n.message:find("\xF0\x9F\x94\x94") then
            icon = '<span class="icon input">IN</span>'
            displayMsg = displayMsg:gsub("\xF0\x9F\x94\x94%s*", "")
        elseif n.message:find("\xE2\x9C\x85") then
            icon = '<span class="icon done">OK</span>'
            displayMsg = displayMsg:gsub("\xE2\x9C\x85%s*", "")
        else
            icon = '<span class="icon other">--</span>'
        end

        local dot = n.read and "" or '<span class="dot"></span>'

        items = items
            .. string.format(
                [[
            <div class="%s" onclick="hs('/click/%d')">
                <div class="row-meta">
                    %s
                    %s
                    %s
                    <span class="time">%s</span>
                </div>
                <div class="row-msg">%s</div>
            </div>
        ]],
                rowClass,
                n.id,
                dot,
                icon,
                tags,
                escapeHtml(n.time),
                escapeHtml(displayMsg)
            )
        ::continue::
    end

    local alphaPct = math.floor(panelState.alpha * 100)

    return string.format(
        [[
<!DOCTYPE html>
<html data-theme="%s">
<head>
<style>
    :root {
        --fs: %dpx;
        /* ── Dark theme (default) ── */
        --bg-body: #161625;
        --bg-header: #1e1e35;
        --bg-even: #1a1a2e;
        --bg-odd: #1e1e35;
        --bg-hover: #282850;
        --bg-active: #303060;
        --bg-hover-subtle: #252545;
        --border: #2e2e4a;
        --text: #d4d4e0;
        --text-bright: #e8e8f8;
        --text-dim: #7a7a9a;
        --text-muted: #5a5a7a;
        --text-faint: #3a3a50;
        --text-empty: #444;
        --accent: #8b8eff;
        --accent-dim: #5a6aee;
        --accent-bg: #252550;
        --accent-border: #5a5a8a;
        --unread-even: #1e1e40;
        --unread-odd: #222248;
        --unread-border: #6a7aff;
        --new-border: #8b8eff;
        --dot: #6a9aff;
        --dot-glow: rgba(106,154,255,0.67);
        --dot-glow-outer: rgba(106,154,255,0.27);
        --dot-pulse: rgba(138,176,255,0.8);
        --dot-pulse-outer: rgba(106,154,255,0.4);
        --icon-input-bg: #2a2a55;  --icon-input-fg: #7eb0ff;
        --icon-done-bg: #1e3a2a;   --icon-done-fg: #6ecc8e;
        --icon-other-bg: #2a2a3a;  --icon-other-fg: #777;
        --tag-project-bg: #2e2518; --tag-project-fg: #e0a060;
        --tag-session-bg: #252548; --tag-session-fg: #7a7abc;
        --badge-bg: #5a5aee;       --badge-fg: #fff;
        --badge-zero-bg: #2a2a44;  --badge-zero-fg: #555;
        --btn-fg: #7a7a9a;         --btn-border: #2e2e4a;
        --btn-hover-bg: #252545;   --btn-hover-fg: #aaa;
        --btn-hover-border: #4a4a6a;
        --danger-fg: #aa5555;      --danger-border: #3a2a2a;
        --danger-hover-bg: #2a1515; --danger-hover-fg: #ff7777;
        --danger-hover-border: #664444;
        --ctrl-fg: #4a4a6a;        --ctrl-label: #5a5a7a;
        --ctrl-val: #7a7a9a;
        --slider-bg: #2a2a48;      --slider-thumb: #8b8eff;
        --slider-thumb-border: #161625;  --slider-thumb-hover: #aaaaff;
        --scroll-track: #1a1a2e;   --scroll-thumb: #4a4a6a;
        --scroll-thumb-hover: #6a6a8a;
        --flash-0: #5a5a90;  --flash-1: #3a3a70;
        --flash-2: #303060;  --flash-3: #3a3a6a;
    }

    /* ── Light theme ── */
    [data-theme="light"] {
        --bg-body: #f4f4f8;
        --bg-header: #ffffff;
        --bg-even: #ffffff;
        --bg-odd: #f7f7fb;
        --bg-hover: #ebebf4;
        --bg-active: #e0e0ec;
        --bg-hover-subtle: #f0f0f8;
        --border: #d8d8e4;
        --text: #333344;
        --text-bright: #111122;
        --text-dim: #666680;
        --text-muted: #8888a0;
        --text-faint: #bbbbcc;
        --text-empty: #aaa;
        --accent: #5555dd;
        --accent-dim: #4444bb;
        --accent-bg: #ebebff;
        --accent-border: #aaaadd;
        --unread-even: #e8ecff;
        --unread-odd: #e0e5ff;
        --unread-border: #4455dd;
        --new-border: #3344ff;
        --dot: #4477ff;
        --dot-glow: rgba(68,119,255,0.5);
        --dot-glow-outer: rgba(68,119,255,0.2);
        --dot-pulse: rgba(85,136,255,0.7);
        --dot-pulse-outer: rgba(68,119,255,0.35);
        --icon-input-bg: #ddeaff;  --icon-input-fg: #2266cc;
        --icon-done-bg: #ddf5e6;   --icon-done-fg: #228844;
        --icon-other-bg: #ececf0;  --icon-other-fg: #999;
        --tag-project-bg: #fff3dd; --tag-project-fg: #aa6600;
        --tag-session-bg: #ebebff; --tag-session-fg: #5555aa;
        --badge-bg: #5555dd;       --badge-fg: #fff;
        --badge-zero-bg: #e0e0ea;  --badge-zero-fg: #999;
        --btn-fg: #666680;         --btn-border: #d8d8e4;
        --btn-hover-bg: #ebebf4;   --btn-hover-fg: #333;
        --btn-hover-border: #bbbbcc;
        --danger-fg: #cc4444;      --danger-border: #eecccc;
        --danger-hover-bg: #fff0f0; --danger-hover-fg: #dd2222;
        --danger-hover-border: #ddaaaa;
        --ctrl-fg: #8888a0;        --ctrl-label: #8888a0;
        --ctrl-val: #666680;
        --slider-bg: #d8d8e4;      --slider-thumb: #5555dd;
        --slider-thumb-border: #ffffff; --slider-thumb-hover: #4444cc;
        --scroll-track: #f0f0f5;   --scroll-thumb: #c8c8d8;
        --scroll-thumb-hover: #a8a8b8;
        --flash-0: #c0c4ff;  --flash-1: #d8daff;
        --flash-2: #e4e6ff;  --flash-3: #dde0ff;
    }

    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
        background: var(--bg-body);
        color: var(--text);
        padding: 0;
        font-size: var(--fs);
        -webkit-user-select: none;
        display: flex;
        flex-direction: column;
        height: 100vh;
    }

    /* ── Header ── */
    .header {
        background: var(--bg-header);
        border-bottom: 1px solid var(--border);
        flex-shrink: 0;
    }
    .header-top {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 14px 6px;
    }
    .title {
        font-size: 13px;
        font-weight: 600;
        color: var(--accent);
        letter-spacing: 0.5px;
    }
    .header-right {
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .badge {
        font-size: 10px;
        color: var(--badge-fg);
        background: var(--badge-bg);
        padding: 1px 7px;
        border-radius: 10px;
        font-weight: 600;
    }
    .badge.zero { background: var(--badge-zero-bg); color: var(--badge-zero-fg); }

    /* ── Filter bar ── */
    .filter-bar {
        display: flex;
        gap: 4px;
        padding: 0 14px 8px;
    }
    .filter-btn {
        font-size: 10px;
        color: var(--text-muted);
        background: none;
        border: 1px solid var(--border);
        border-radius: 4px;
        padding: 2px 10px;
        cursor: pointer;
        transition: all 0.15s;
    }
    .filter-btn:hover { background: var(--bg-hover-subtle); color: var(--btn-hover-fg); }
    .filter-btn.active { color: var(--accent); border-color: var(--accent-border); background: var(--accent-bg); }

    /* ── Buttons ── */
    .hdr-btn {
        font-size: 10px;
        color: var(--btn-fg);
        background: none;
        border: 1px solid var(--btn-border);
        border-radius: 4px;
        padding: 2px 7px;
        cursor: pointer;
        transition: all 0.15s;
    }
    .hdr-btn:hover { background: var(--btn-hover-bg); color: var(--btn-hover-fg); border-color: var(--btn-hover-border); }
    .hdr-btn.danger { color: var(--danger-fg); border-color: var(--danger-border); }
    .hdr-btn.danger:hover { background: var(--danger-hover-bg); color: var(--danger-hover-fg); border-color: var(--danger-hover-border); }

    /* ── List ── */
    .list {
        overflow-y: auto;
        flex: 1;
        padding: 4px 0;
    }
    .list::-webkit-scrollbar { width: 8px; }
    .list::-webkit-scrollbar-track { background: var(--scroll-track); border-radius: 4px; }
    .list::-webkit-scrollbar-thumb { background: var(--scroll-thumb); border-radius: 4px; border: 1px solid var(--scroll-track); }
    .list::-webkit-scrollbar-thumb:hover { background: var(--scroll-thumb-hover); }

    /* ── Item rows ── */
    .item {
        padding: 6px 14px 7px;
        display: flex;
        flex-direction: column;
        gap: 3px;
        transition: background 0.2s, border-left-color 0.2s;
        cursor: pointer;
        border-left: 3px solid transparent;
    }
    .item.even { background: var(--bg-even); }
    .item.odd  { background: var(--bg-odd); }
    .item:hover { background: var(--bg-hover); border-left-color: var(--accent); }
    .item:active { background: var(--bg-active); }

    /* Read items: dim everything */
    .item.read { border-left-color: transparent; }
    .item.read .row-msg { color: var(--text-muted); }
    .item.read .time { color: var(--text-faint); }
    .item.read .icon { opacity: 0.4; }
    .item.read .tag { opacity: 0.4; }

    /* Unread items: strong accent */
    .item.unread { border-left-color: var(--unread-border); }
    .item.unread.even { background: var(--unread-even); }
    .item.unread.odd  { background: var(--unread-odd); }
    .item.unread .row-msg { color: var(--text-bright); font-weight: 500; }
    .item.unread .time { color: var(--text-dim); }

    /* Newest unread: entrance animation */
    .item.new {
        animation: flashIn 2.5s ease-out;
        border-left-color: var(--new-border);
    }
    @keyframes flashIn {
        0%%   { background: var(--flash-0); border-left-color: var(--accent); }
        15%%  { background: var(--flash-1); }
        30%%  { background: var(--flash-0); }
        50%%  { background: var(--flash-2); }
        70%%  { background: var(--flash-3); }
        100%% { background: transparent; border-left-color: var(--unread-border); }
    }

    /* ── Row layout ── */
    .row-meta { display: flex; align-items: center; gap: 6px; }
    .row-msg { padding-left: 12px; line-height: 1.4; font-size: var(--fs); }

    /* ── Unread dot (pulse) ── */
    .dot {
        width: 8px;
        height: 8px;
        background: var(--dot);
        border-radius: 50%%;
        flex-shrink: 0;
        box-shadow: 0 0 6px var(--dot-glow), 0 0 12px var(--dot-glow-outer);
        animation: pulse 2s ease-in-out infinite;
    }
    @keyframes pulse {
        0%%, 100%% { box-shadow: 0 0 6px var(--dot-glow), 0 0 12px var(--dot-glow-outer); }
        50%% { box-shadow: 0 0 10px var(--dot-pulse), 0 0 20px var(--dot-pulse-outer); }
    }

    /* ── Icons ── */
    .icon {
        font-size: calc(var(--fs) * 0.7);
        font-weight: 700;
        padding: 2px 5px;
        border-radius: 3px;
        font-family: "SF Mono", Menlo, monospace;
        flex-shrink: 0;
    }
    .icon.input { background: var(--icon-input-bg); color: var(--icon-input-fg); }
    .icon.done  { background: var(--icon-done-bg); color: var(--icon-done-fg); }
    .icon.other { background: var(--icon-other-bg); color: var(--icon-other-fg); }

    /* ── Time ── */
    .time {
        color: var(--text-muted);
        font-size: calc(var(--fs) * 0.85);
        font-family: "SF Mono", Menlo, monospace;
        flex-shrink: 0;
        margin-left: auto;
    }

    /* ── Tags ── */
    .tag {
        font-size: calc(var(--fs) * 0.77);
        padding: 1px 6px;
        border-radius: 4px;
        font-family: "SF Mono", Menlo, monospace;
        max-width: 120px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        flex-shrink: 0;
    }
    .tag.project { color: var(--tag-project-fg); background: var(--tag-project-bg); }
    .tag.session { color: var(--tag-session-fg); background: var(--tag-session-bg); }

    .empty { color: var(--text-empty); text-align: center; padding: 60px 0; }

    /* ── Controls footer ── */
    .controls {
        flex-shrink: 0;
        background: var(--bg-header);
        border-top: 1px solid var(--border);
    }
    .ctrl-toggle {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 4px;
        cursor: pointer;
        color: var(--ctrl-fg);
        font-size: 10px;
        transition: color 0.15s;
    }
    .ctrl-toggle:hover { color: var(--accent); }
    .ctrl-panel {
        display: none;
        padding: 6px 14px 8px;
        gap: 6px;
        flex-direction: column;
    }
    .ctrl-panel.open { display: flex; }
    .ctrl-row {
        display: flex;
        align-items: center;
        gap: 8px;
        width: 100%%;
    }
    .ctrl-label {
        font-size: 10px;
        color: var(--ctrl-label);
        flex-shrink: 0;
        min-width: 48px;
    }
    .ctrl-val {
        font-size: 10px;
        color: var(--ctrl-val);
        flex-shrink: 0;
        min-width: 32px;
        text-align: right;
    }
    input[type="range"] {
        -webkit-appearance: none;
        flex: 1;
        height: 4px;
        background: var(--slider-bg);
        border-radius: 2px;
        outline: none;
    }
    input[type="range"]::-webkit-slider-thumb {
        -webkit-appearance: none;
        width: 14px;
        height: 14px;
        background: var(--slider-thumb);
        border-radius: 50%%;
        cursor: pointer;
        border: 2px solid var(--slider-thumb-border);
    }
    input[type="range"]::-webkit-slider-thumb:hover {
        background: var(--slider-thumb-hover);
    }

    /* ── Theme toggle ── */
    .theme-btns {
        display: flex;
        gap: 4px;
        flex: 1;
    }
    .theme-btn {
        font-size: 10px;
        color: var(--btn-fg);
        background: none;
        border: 1px solid var(--btn-border);
        border-radius: 4px;
        padding: 2px 10px;
        cursor: pointer;
        transition: all 0.15s;
        flex: 1;
        text-align: center;
    }
    .theme-btn:hover { background: var(--btn-hover-bg); color: var(--btn-hover-fg); }
    .theme-btn.active { color: var(--accent); border-color: var(--accent-border); background: var(--accent-bg); }
</style>
<script>
function hs(path) {
    var x = new XMLHttpRequest();
    x.open('GET', 'http://localhost:%d' + path + '?t=' + Date.now());
    x.send();
}
</script>
</head>
<body>
    <div class="header">
        <div class="header-top">
            <span class="title">Claude Code</span>
            <div class="header-right">
                <span class="badge%s">%s</span>
                <div class="hdr-btn" onclick="hs('/clear')">Clear</div>
                <div class="hdr-btn danger" onclick="hs('/quit')">Quit</div>
            </div>
        </div>
        <div class="filter-bar">
            <div class="filter-btn%s" onclick="hs('/filter/all')">All</div>
            <div class="filter-btn%s" onclick="hs('/filter/input')">IN</div>
            <div class="filter-btn%s" onclick="hs('/filter/done')">OK</div>
        </div>
    </div>
    <div class="list">
        %s
    </div>
    <div class="controls">
        <div class="ctrl-toggle" onclick="var p=document.getElementById('ctrlPanel');p.classList.toggle('open');this.textContent=p.classList.contains('open')?'▾ Settings':'▸ Settings'">▸ Settings</div>
        <div class="ctrl-panel" id="ctrlPanel">
            <div class="ctrl-row">
                <span class="ctrl-label">Theme</span>
                <div class="theme-btns">
                    <div class="theme-btn%s" onclick="hs('/theme/dark')">Dark</div>
                    <div class="theme-btn%s" onclick="hs('/theme/light')">Light</div>
                </div>
            </div>
            <div class="ctrl-row">
                <span class="ctrl-label">Opacity</span>
                <input type="range" min="10" max="100" value="%d"
                    oninput="document.getElementById('alphaVal').textContent=this.value+'%%'"
                    onchange="hs('/alpha/'+(this.value/100))">
                <span class="ctrl-val" id="alphaVal">%d%%</span>
            </div>
            <div class="ctrl-row">
                <span class="ctrl-label">Font</span>
                <input type="range" min="10" max="20" value="%d"
                    oninput="document.getElementById('fontVal').textContent=this.value+'px'; document.documentElement.style.setProperty('--fs',this.value+'px')"
                    onchange="hs('/fontsize/'+this.value)">
                <span class="ctrl-val" id="fontVal">%dpx</span>
            </div>
        </div>
    </div>
</body>
</html>
    ]],
        panelState.theme,
        panelState.fontSize,
        cfg.port,
        unreadCount == 0 and " zero" or "",
        unreadCount > 0 and tostring(unreadCount) or "0",
        panelState.filter == "all" and " active" or "",
        panelState.filter == "input" and " active" or "",
        panelState.filter == "done" and " active" or "",
        items == "" and '<div class="empty">No notifications</div>' or items,
        panelState.theme == "dark" and " active" or "",
        panelState.theme == "light" and " active" or "",
        alphaPct,
        alphaPct,
        panelState.fontSize,
        panelState.fontSize
    )
end

function ClaudeNotify.updatePanel()
    if webview then
        webview:html(ClaudeNotify.generateHTML())
    end
end

function ClaudeNotify.show()
    if not webview then
        ClaudeNotify.createPanel()
    end
    webview:html(ClaudeNotify.generateHTML())
    webview:show()
    isVisible = true
end

function ClaudeNotify.hide()
    if webview then
        webview:hide()
    end
    isVisible = false
end

function ClaudeNotify.toggle()
    if isVisible then
        ClaudeNotify.hide()
    else
        ClaudeNotify.show()
    end
end

function ClaudeNotify.clear()
    notifications = {}
    ClaudeNotify.updatePanel()
end

-- Hotkey (from config)
hs.hotkey.bind(cfg.hotkey_mods, cfg.hotkey_key, function()
    ClaudeNotify.toggle()
end)

return ClaudeNotify
