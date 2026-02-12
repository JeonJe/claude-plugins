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
    filter = "all", -- "all", "input", "done"
    fontSize = 13,
}

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

function ClaudeNotify.quit()
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
        -- Strip emoji prefix from display message to avoid redundancy with badge
        local icon = ""
        local displayMsg = n.message
        if n.message:find("\xF0\x9F\x94\x94") then -- bell emoji
            icon = '<span class="icon input">IN</span>'
            displayMsg = displayMsg:gsub("\xF0\x9F\x94\x94%s*", "")
        elseif n.message:find("\xE2\x9C\x85") then -- check emoji
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
<html>
<head>
<style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
        background: #161625;
        color: #d4d4e0;
        padding: 0;
        font-size: %dpx;
        -webkit-user-select: none;
        display: flex;
        flex-direction: column;
        height: 100vh;
    }
    .header {
        background: #1e1e35;
        border-bottom: 1px solid #2e2e4a;
        flex-shrink: 0;
    }
    .header-top {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 14px 6px;
    }
    .filter-bar {
        display: flex;
        gap: 4px;
        padding: 0 14px 8px;
    }
    .filter-btn {
        font-size: 10px;
        color: #5a5a7a;
        background: none;
        border: 1px solid #2e2e4a;
        border-radius: 4px;
        padding: 2px 10px;
        cursor: pointer;
        transition: all 0.15s;
    }
    .filter-btn:hover { background: #252545; color: #aaa; }
    .filter-btn.active { color: #8b8eff; border-color: #5a5a8a; background: #252550; }
    .title {
        font-size: 13px;
        font-weight: 600;
        color: #8b8eff;
        letter-spacing: 0.5px;
    }
    .header-right {
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .badge {
        font-size: 10px;
        color: #fff;
        background: #5a5aee;
        padding: 1px 7px;
        border-radius: 10px;
        font-weight: 600;
    }
    .badge.zero { background: #2a2a44; color: #555; }
    .hdr-btn {
        font-size: 10px;
        color: #7a7a9a;
        background: none;
        border: 1px solid #2e2e4a;
        border-radius: 4px;
        padding: 2px 7px;
        cursor: pointer;
        transition: all 0.15s;
    }
    .hdr-btn:hover { background: #252545; color: #aaa; border-color: #4a4a6a; }
    .hdr-btn.active { color: #8b8eff; border-color: #5a5a8a; background: #252550; }
    .hdr-btn.danger { color: #aa5555; border-color: #3a2a2a; }
    .hdr-btn.danger:hover { background: #2a1515; color: #ff7777; border-color: #664444; }
    .list {
        overflow-y: auto;
        flex: 1;
        padding: 4px 0;
    }
    .list::-webkit-scrollbar {
        width: 8px;
    }
    .list::-webkit-scrollbar-track {
        background: #1a1a2e;
        border-radius: 4px;
    }
    .list::-webkit-scrollbar-thumb {
        background: #4a4a6a;
        border-radius: 4px;
        border: 1px solid #1a1a2e;
    }
    .list::-webkit-scrollbar-thumb:hover {
        background: #6a6a8a;
    }
    .item {
        padding: 6px 14px 7px;
        display: flex;
        flex-direction: column;
        gap: 3px;
        transition: background 0.15s;
        cursor: pointer;
        border-left: 3px solid transparent;
    }
    .item.even { background: #1a1a2e; }
    .item.odd  { background: #1e1e35; }
    .item:hover {
        background: #282850;
        border-left-color: #8b8eff;
    }
    .item:active { background: #303060; }
    .item.new {
        animation: flashIn 2s ease-out;
        border-left-color: #6a6aff;
    }
    @keyframes flashIn {
        0%%   { background: #4a4a80; }
        15%%  { background: #252550; }
        30%%  { background: #4a4a80; }
        50%%  { background: #303060; }
        70%%  { background: #3a3a70; }
        100%% { background: transparent; }
    }

    .row-meta {
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .row-msg {
        padding-left: 12px;
        line-height: 1.4;
        font-size: 12.5px;
    }

    .item.read .row-msg { color: #6a6a80; }
    .item.read .time { color: #3a3a50; }
    .item.read .icon { opacity: 0.4; }
    .item.read .tag { opacity: 0.4; }
    .item.unread .row-msg { color: #e0e0f0; font-weight: 500; }

    .dot {
        width: 6px;
        height: 6px;
        background: #5a8aff;
        border-radius: 50%%;
        flex-shrink: 0;
        box-shadow: 0 0 4px #5a8aff88;
    }
    .icon {
        font-size: 9px;
        font-weight: 700;
        padding: 2px 5px;
        border-radius: 3px;
        font-family: "SF Mono", Menlo, monospace;
        flex-shrink: 0;
    }
    .icon.input { background: #2a2a55; color: #7eb0ff; }
    .icon.done  { background: #1e3a2a; color: #6ecc8e; }
    .icon.other { background: #2a2a3a; color: #777; }
    .time {
        color: #5a5a7a;
        font-size: 11px;
        font-family: "SF Mono", Menlo, monospace;
        flex-shrink: 0;
        margin-left: auto;
    }
    .tag {
        font-size: 10px;
        padding: 1px 6px;
        border-radius: 4px;
        font-family: "SF Mono", Menlo, monospace;
        max-width: 120px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        flex-shrink: 0;
    }
    .tag.project {
        color: #e0a060;
        background: #2e2518;
    }
    .tag.session {
        color: #7a7abc;
        background: #252548;
    }
    .empty {
        color: #444;
        text-align: center;
        padding: 60px 0;
        font-size: 13px;
    }

    .controls {
        flex-shrink: 0;
        padding: 6px 14px;
        background: #1e1e35;
        border-top: 1px solid #2e2e4a;
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 4px 8px;
    }
    .ctrl-row {
        display: flex;
        align-items: center;
        gap: 8px;
        width: 100%%;
    }
    .ctrl-label {
        font-size: 10px;
        color: #5a5a7a;
        flex-shrink: 0;
        min-width: 28px;
    }
    input[type="range"] {
        -webkit-appearance: none;
        flex: 1;
        height: 4px;
        background: #2a2a48;
        border-radius: 2px;
        outline: none;
    }
    input[type="range"]::-webkit-slider-thumb {
        -webkit-appearance: none;
        width: 14px;
        height: 14px;
        background: #8b8eff;
        border-radius: 50%%;
        cursor: pointer;
        border: 2px solid #161625;
    }
    input[type="range"]::-webkit-slider-thumb:hover {
        background: #aaaaff;
    }
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
        <div class="ctrl-row">
            <span class="ctrl-label" id="alphaLabel">%d%%</span>
            <input type="range" min="10" max="100" value="%d"
                oninput="document.getElementById('alphaLabel').textContent=this.value+'%%'"
                onchange="hs('/alpha/'+(this.value/100))">
        </div>
        <div class="ctrl-row">
            <span class="ctrl-label" id="fontLabel">%dpx</span>
            <input type="range" min="10" max="20" value="%d"
                oninput="document.getElementById('fontLabel').textContent=this.value+'px'; document.body.style.fontSize=this.value+'px'"
                onchange="hs('/fontsize/'+this.value)">
        </div>
    </div>
</body>
</html>
    ]],
        panelState.fontSize,
        cfg.port,
        unreadCount == 0 and " zero" or "",
        unreadCount > 0 and tostring(unreadCount) or "0",
        panelState.filter == "all" and " active" or "",
        panelState.filter == "input" and " active" or "",
        panelState.filter == "done" and " active" or "",
        items == "" and '<div class="empty">No notifications</div>' or items,
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
