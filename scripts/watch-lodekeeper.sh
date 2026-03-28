#!/usr/bin/env bash
# watch-lodekeeper.sh — 4-panel tmux dashboard to observe Lodekeeper activity
# Pure read-only observation. Modifies nothing.
set -euo pipefail

SESSION_NAME="watch-lodekeeper"
OC_DIR="$HOME/.openclaw"
WORKSPACE="$OC_DIR/workspace"
SESSIONS_DIR="$OC_DIR/agents/main/sessions"

# Colors
C_RESET='\033[0m'
C_YELLOW='\033[1;33m'
C_CYAN='\033[1;36m'
C_GREEN='\033[1;32m'
C_DIM='\033[2m'
C_MAGENTA='\033[1;35m'
C_BOLD='\033[1m'

# ── Helpers ──────────────────────────────────────────────────────────────────

find_active_session_jsonl() {
  # Find the most recently modified JSONL (the active main session)
  ls -t "$SESSIONS_DIR"/*.jsonl 2>/dev/null | head -1
}

find_today_notes() {
  local today
  today=$(date -u +%F)
  local f="$WORKSPACE/memory/${today}.md"
  if [[ -f "$f" ]]; then
    echo "$f"
  else
    # Create it so tail -f has something to watch
    touch "$f"
    echo "$f"
  fi
}

# ── Panel scripts (written to /tmp, executed inside tmux panes) ───────────

write_panel_scripts() {
  # Panel 1: Exec commands from session JSONL (top-left)
  cat > /tmp/wl-exec-feed.sh << 'P1'
#!/usr/bin/env bash
SESSIONS_DIR="$HOME/.openclaw/agents/main/sessions"
echo -e "\033[1;32m━━━ 🖥️  Command Executions ━━━\033[0m"
echo ""

active_jsonl() { ls -t "$SESSIONS_DIR"/*.jsonl 2>/dev/null | head -1; }

# Watch for new lines and extract exec commands
tail -n 0 -F "$(active_jsonl)" 2>/dev/null | python3 -u -c "
import json, sys, os
from datetime import datetime

for line in sys.stdin:
    try:
        d = json.loads(line.strip())
        msg = d.get('message', d)
        content = msg.get('content', [])
        if not isinstance(content, list): continue
        ts = d.get('timestamp', '')
        if ts:
            try:
                t = datetime.fromisoformat(ts.replace('Z','+00:00'))
                ts_str = t.strftime('%H:%M:%S')
            except: ts_str = ''
        else:
            ts_str = datetime.utcnow().strftime('%H:%M:%S')
        for c in content:
            if not isinstance(c, dict): continue
            if c.get('name') == 'exec':
                args_raw = c.get('arguments', '{}')
                args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                cmd = args.get('command', '')
                if cmd:
                    # Truncate long commands
                    display = cmd.replace('\n', ' ↵ ')
                    if len(display) > 200: display = display[:197] + '...'
                    print(f'\033[2m{ts_str}\033[0m \033[1;32m$\033[0m {display}', flush=True)
    except: pass
"
P1

  # Panel 2: Daily notes feed (top-right)
  cat > /tmp/wl-notes-feed.sh << 'P2'
#!/usr/bin/env bash
WORKSPACE="$HOME/.openclaw/workspace"
echo -e "\033[1;33m━━━ 📝 Daily Notes (live) ━━━\033[0m"
echo ""

today=$(date -u +%F)
notes="$WORKSPACE/memory/${today}.md"
[[ -f "$notes" ]] || touch "$notes"

# Show last 10 lines for context, then follow
echo -e "\033[2m--- existing entries ---\033[0m"
tail -10 "$notes" 2>/dev/null
echo -e "\033[2m--- live feed ---\033[0m"
tail -n 0 -F "$notes" 2>/dev/null
P2

  # Panel 3: Session thinking + tool calls (bottom-left)
  cat > /tmp/wl-session-log.sh << 'P3'
#!/usr/bin/env bash
SESSIONS_DIR="$HOME/.openclaw/agents/main/sessions"
echo -e "\033[1;36m━━━ 🧠 Session Log (thinking + tools) ━━━\033[0m"
echo ""

active_jsonl() { ls -t "$SESSIONS_DIR"/*.jsonl 2>/dev/null | head -1; }

tail -n 0 -F "$(active_jsonl)" 2>/dev/null | python3 -u -c "
import json, sys
from datetime import datetime

for line in sys.stdin:
    try:
        d = json.loads(line.strip())
        msg = d.get('message', d)
        role = msg.get('role', '')
        content = msg.get('content', [])
        if not isinstance(content, list): continue

        ts = d.get('timestamp', '')
        if ts:
            try:
                t = datetime.fromisoformat(ts.replace('Z','+00:00'))
                ts_str = t.strftime('%H:%M:%S')
            except: ts_str = ''
        else:
            ts_str = datetime.utcnow().strftime('%H:%M:%S')

        for c in content:
            if not isinstance(c, dict): continue
            ctype = c.get('type', '')

            if ctype == 'thinking':
                text = c.get('thinking', '')
                # Show first 300 chars of thinking
                display = text.replace('\n', ' ').strip()
                if len(display) > 300: display = display[:297] + '...'
                if display:
                    print(f'\033[2m{ts_str}\033[0m \033[1;33m🧠\033[0m {display}', flush=True)

            elif ctype == 'toolCall':
                name = c.get('name', '?')
                args_raw = c.get('arguments', '{}')
                try:
                    args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                except: args = {}
                # Compact display
                if name == 'exec':
                    cmd = args.get('command', '')[:80]
                    print(f'\033[2m{ts_str}\033[0m \033[1;36m🔧 {name}\033[0m {cmd}', flush=True)
                elif name == 'read':
                    path = args.get('file_path', args.get('path', ''))
                    print(f'\033[2m{ts_str}\033[0m \033[1;36m📖 {name}\033[0m {path}', flush=True)
                elif name == 'edit':
                    path = args.get('file_path', args.get('path', ''))
                    print(f'\033[2m{ts_str}\033[0m \033[1;36m✏️  {name}\033[0m {path}', flush=True)
                elif name == 'message':
                    action = args.get('action', '')
                    target = args.get('target', '')
                    print(f'\033[2m{ts_str}\033[0m \033[1;35m💬 {name}\033[0m {action} → {target}', flush=True)
                elif name in ('web_search', 'web_fetch'):
                    q = args.get('query', args.get('url', ''))[:80]
                    print(f'\033[2m{ts_str}\033[0m \033[1;36m🌐 {name}\033[0m {q}', flush=True)
                elif name in ('sessions_spawn', 'sessions_send'):
                    label = args.get('label', args.get('sessionKey', ''))[:60]
                    print(f'\033[2m{ts_str}\033[0m \033[1;35m🤖 {name}\033[0m {label}', flush=True)
                else:
                    summary = str(args)[:80]
                    print(f'\033[2m{ts_str}\033[0m \033[1;36m🔧 {name}\033[0m {summary}', flush=True)

            elif ctype == 'text' and role == 'assistant':
                text = c.get('text', '').strip()
                if text and not text.startswith('NO_REPLY') and not text.startswith('HEARTBEAT'):
                    display = text.replace('\n', ' ')
                    if len(display) > 200: display = display[:197] + '...'
                    print(f'\033[2m{ts_str}\033[0m \033[1m💬\033[0m {display}', flush=True)
    except: pass
"
P3

  # Panel 4: Workspace file diffs with git-style diffs (bottom-right)
  cat > /tmp/wl-workspace-diffs.sh << 'P4'
#!/usr/bin/env bash
WORKSPACE="$HOME/.openclaw/workspace"
SHADOW_DIR="/tmp/wl-shadow"
echo -e "\033[1;35m━━━ 📂 Workspace Changes ━━━\033[0m"
echo ""

# Files to watch
WATCH_FILES=(MEMORY.md BACKLOG.md STATE.md HEARTBEAT.md TOOLS.md)

# Create shadow copies for diffing
mkdir -p "$SHADOW_DIR"
for f in "${WATCH_FILES[@]}"; do
    [[ -f "$WORKSPACE/$f" ]] && cp "$WORKSPACE/$f" "$SHADOW_DIR/$f" 2>/dev/null
done
# Also shadow today's daily notes
today=$(date -u +%F)
notes="$WORKSPACE/memory/${today}.md"
[[ -f "$notes" ]] && cp "$notes" "$SHADOW_DIR/daily-notes.md" 2>/dev/null || touch "$SHADOW_DIR/daily-notes.md"

show_diff() {
    local label="$1"
    local shadow="$2"
    local current="$3"
    local ts
    ts=$(date -u +%H:%M:%S)

    if [[ ! -f "$shadow" ]]; then
        # New file — show last 5 lines
        echo -e "\033[2m${ts}\033[0m \033[1;35m✏️  ${label}\033[0m \033[1;32m(new file)\033[0m"
        tail -5 "$current" | sed 's/^/  \x1b[32m+ \x1b[0m/'
    else
        local diff_output
        diff_output=$(diff -u "$shadow" "$current" 2>/dev/null | tail -n +3)
        if [[ -n "$diff_output" ]]; then
            echo -e "\033[2m${ts}\033[0m \033[1;35m✏️  ${label}\033[0m"
            echo "$diff_output" | while IFS= read -r line; do
                if [[ "$line" == +* && "$line" != +++* ]]; then
                    echo -e "  \033[32m${line}\033[0m"
                elif [[ "$line" == -* && "$line" != ---* ]]; then
                    echo -e "  \033[31m${line}\033[0m"
                elif [[ "$line" == @@* ]]; then
                    echo -e "  \033[36m${line}\033[0m"
                fi
            done
            echo ""
        fi
    fi
    # Update shadow
    cp "$current" "$shadow" 2>/dev/null
}

if ! command -v inotifywait &>/dev/null; then
    echo -e "\033[2minotify-tools not installed, using poll mode (5s)\033[0m"
    echo ""
    while true; do
        for f in "${WATCH_FILES[@]}"; do
            [[ -f "$WORKSPACE/$f" ]] && show_diff "$f" "$SHADOW_DIR/$f" "$WORKSPACE/$f"
        done
        [[ -f "$notes" ]] && show_diff "daily-notes" "$SHADOW_DIR/daily-notes.md" "$notes"
        sleep 5
    done
else
    # Build watch list
    WATCH_ARGS=()
    for f in "${WATCH_FILES[@]}"; do
        [[ -f "$WORKSPACE/$f" ]] && WATCH_ARGS+=("$WORKSPACE/$f")
    done
    WATCH_ARGS+=("$WORKSPACE/memory/")

    while true; do
        changed=$(inotifywait -q -e modify,create "${WATCH_ARGS[@]}" 2>/dev/null)
        # Small delay to let writes finish
        sleep 0.3

        dir=$(echo "$changed" | awk '{print $1}')
        if [[ "$dir" == *"/memory/"* ]]; then
            # Daily notes change
            [[ -f "$notes" ]] && show_diff "daily-notes (${today})" "$SHADOW_DIR/daily-notes.md" "$notes"
        else
            # Workspace root file
            for f in "${WATCH_FILES[@]}"; do
                if [[ -f "$WORKSPACE/$f" ]]; then
                    csum_old=$(md5sum "$SHADOW_DIR/$f" 2>/dev/null | cut -d' ' -f1)
                    csum_new=$(md5sum "$WORKSPACE/$f" 2>/dev/null | cut -d' ' -f1)
                    [[ "$csum_old" != "$csum_new" ]] && show_diff "$f" "$SHADOW_DIR/$f" "$WORKSPACE/$f"
                fi
            done
        fi
    done
fi
P4

  chmod +x /tmp/wl-exec-feed.sh /tmp/wl-notes-feed.sh /tmp/wl-session-log.sh /tmp/wl-workspace-diffs.sh
}

# ── Main ─────────────────────────────────────────────────────────────────────

main() {
  # Kill existing session if any
  tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true

  write_panel_scripts

  # Create tmux session with 4 panes
  # Layout: top-left | top-right
  #         bot-left | bot-right

  tmux new-session -d -s "$SESSION_NAME" -x 200 -y 50

  # Pane 0 (top-left): Exec commands
  tmux send-keys -t "$SESSION_NAME" "bash /tmp/wl-exec-feed.sh" C-m

  # Split horizontally → pane 1 (top-right): Daily notes
  tmux split-window -h -t "$SESSION_NAME"
  tmux send-keys -t "$SESSION_NAME" "bash /tmp/wl-notes-feed.sh" C-m

  # Split pane 0 vertically → pane 2 (bottom-left): Session log
  tmux split-window -v -t "${SESSION_NAME}:0.0"
  tmux send-keys -t "$SESSION_NAME" "bash /tmp/wl-session-log.sh" C-m

  # Split pane 1 vertically → pane 3 (bottom-right): Workspace diffs
  tmux split-window -v -t "${SESSION_NAME}:0.1"
  tmux send-keys -t "$SESSION_NAME" "bash /tmp/wl-workspace-diffs.sh" C-m

  # Even out the layout
  tmux select-layout -t "$SESSION_NAME" tiled

  echo "Dashboard started! Attach with:"
  echo "  tmux attach -t $SESSION_NAME"
  echo ""
  echo "Panels:"
  echo "  Top-left:     🖥️  Command executions"
  echo "  Top-right:    📝 Daily notes feed"
  echo "  Bottom-left:  🧠 Session thinking + tools"
  echo "  Bottom-right: 📂 Workspace file changes"
  echo ""
  echo "Detach: Ctrl-B d  |  Kill: tmux kill-session -t $SESSION_NAME"
}

main "$@"
