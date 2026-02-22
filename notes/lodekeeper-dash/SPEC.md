# Lodekeeper Dashboard — Spec

## Problem
Nico needs visibility into what I (Lodekeeper) am doing at all times — tasks, tracked threads, running agents, token usage, cron jobs, and live work streams. Currently this information is scattered across markdown files (BACKLOG.md, HEARTBEAT.md, memory/), Discord threads, GitHub PRs, and OpenClaw internals. A unified dashboard will consolidate everything into one interactive, secure UI.

## Requirements (from Nico)
1. **Task Board** — Kanban/sprint-style board visualizing backlog tasks (Todo, In Progress, Done, Needs Feedback). Writable by Nico too. Drag-and-drop to move tasks between columns.
2. **Discord & GitHub Tracking** — Which threads/discussions I'm following, with details + links. Same for GitHub PRs/issues.
3. **Periodic Jobs Overview** — All heartbeats and cron jobs in a concise table.
4. **Token Usage & Agent Overview** — Current session usage, running sub-agents, CLI agents, what they're working on.
5. **Live Work Stream** — Panel that streams output from kurtosis runs, debug sessions, coding agents — real-time observability.
6. **Status Indicator** — Am I busy? Idle? What am I currently working on?
7. **Security** — Auth required, secure enough for public exposure. Only Nico and invited friends can access.
8. **No private data in repo** — Config/secrets via environment variables.

## Tech Stack

### Backend: Node.js + Express + TypeScript
- Single process, lightweight
- REST API for CRUD operations
- WebSocket (ws) for real-time updates (task changes, live streams, agent status)
- Server-Sent Events fallback for simpler consumers
- File-based storage (JSON) — no database dependency
- Reads from workspace files (BACKLOG.md, HEARTBEAT.md, memory/) and OpenClaw APIs

### Frontend: React 19 + Vite + TypeScript
- Single-page application
- Tailwind CSS for styling (utility-first, rapid iteration)
- @dnd-kit for drag-and-drop kanban
- Recharts or lightweight chart lib for token usage visualization
- xterm.js for terminal streaming panel
- Built assets served by Express in production

### Auth & Security
- **JWT-based authentication** with httpOnly secure cookies
- **bcrypt-hashed passwords** stored in `config.json` (gitignored)
- **Invite links** — Nico can generate time-limited invite tokens for friends
- **Rate limiting** on auth endpoints (express-rate-limit)
- **Helmet.js** for security headers (CSP, HSTS, X-Frame-Options, etc.)
- **CORS** restricted to dashboard origin only
- No default credentials — first-run setup wizard creates admin account
- Session expiry: 7 days, refresh on activity

### Deployment
- Port 7777 (configurable via env)
- Development: `pnpm dev` (Vite dev server + Express with hot reload)
- Production: `pnpm build && pnpm start` (Vite builds static, Express serves)
- Can sit behind nginx/caddy reverse proxy for HTTPS

## Architecture

```
┌─────────────────────────────────────────────────┐
│                    Browser                       │
│  React SPA (Vite)                               │
│  ┌──────────┬──────────┬──────────┬──────────┐ │
│  │ Task     │ Tracking │ Agents & │ Live     │ │
│  │ Board    │ Panel    │ Jobs     │ Stream   │ │
│  └──────────┴──────────┴──────────┴──────────┘ │
│           ↕ REST + WebSocket                    │
└─────────────────────────────────────────────────┘
                    ↕
┌─────────────────────────────────────────────────┐
│              Express Server (7777)               │
│  ┌─────────────────────────────────────────────┐│
│  │ Auth Middleware (JWT + bcrypt)               ││
│  ├─────────────────────────────────────────────┤│
│  │ REST API                                    ││
│  │  /api/auth/*        - login, invite, verify ││
│  │  /api/tasks/*       - CRUD + reorder        ││
│  │  /api/tracking/*    - discord, github       ││
│  │  /api/agents/*      - sub-agents, sessions  ││
│  │  /api/jobs/*        - cron, heartbeat       ││
│  │  /api/status        - agent status          ││
│  │  /api/usage         - token usage           ││
│  ├─────────────────────────────────────────────┤│
│  │ WebSocket Hub                               ││
│  │  - Task board sync (multi-user)             ││
│  │  - Live terminal streams                    ││
│  │  - Agent status push                        ││
│  │  - Notification feed                        ││
│  ├─────────────────────────────────────────────┤│
│  │ Data Collectors (polling)                   ││
│  │  - WorkspaceSync: BACKLOG.md → tasks        ││
│  │  - GitHubCollector: PRs, issues, notifs     ││
│  │  - DiscordCollector: thread activity         ││
│  │  - AgentCollector: sessions, processes      ││
│  │  - CronCollector: job schedules, history    ││
│  │  - UsageCollector: token/cost tracking      ││
│  └─────────────────────────────────────────────┘│
│              ↕ File I/O + CLI                    │
│  ┌─────────────────────────────────────────────┐│
│  │ Storage (data/)                             ││
│  │  tasks.json, config.json, sessions.json     ││
│  │  + reads workspace markdown files           ││
│  └─────────────────────────────────────────────┘│
└─────────────────────────────────────────────────┘
```

## UI Layout

### Navigation
- Sidebar with sections: Dashboard, Tasks, Tracking, Agents, Jobs, Stream
- Collapsible on mobile
- Status badge in header (🟢 Idle, 🟡 Working, 🔴 Busy)

### 1. Dashboard (Home)
- **Status Card**: Current activity, model, uptime, context usage %
- **Task Summary**: Counts per column (Todo: 3, In Progress: 2, Done: 8, Feedback: 1)
- **Active Agents**: Cards showing running sub-agents with task descriptions
- **Recent Activity Feed**: Last 10 actions (PR comments, task moves, cron triggers)
- **Quick Stats**: Token usage today, messages sent, PRs reviewed

### 2. Task Board
- **Kanban columns**: Backlog | Todo | In Progress | Review/Feedback | Done
- **Task cards** show: title, priority badge (🔴🟡🟢), source, assignee (me/Nico), timestamp
- **Drag-and-drop** between columns
- **Click to expand**: Full description, linked PRs, discussion links, notes
- **Add task**: Quick-add form for Nico
- **Filters**: By priority, assignee, source
- **Sync indicator**: Shows when tasks were last synced from BACKLOG.md

### 3. Tracking Panel
- **Discord Threads** table: Thread name, channel, last message, participants, link, status (active/quiet/archived)
- **GitHub PRs** table: PR #, title, status (open/merged/closed), CI status, review status, link
- **GitHub Issues**: Watched issues with last activity
- **Expandable rows** with recent messages/comments preview

### 4. Agents & Sessions
- **Active Sessions**: Cards for each running session (main, sub-agents)
  - Model, token usage, current task, uptime
  - Quick actions: view history, send message
- **CLI Agents**: Running Codex/Claude processes
  - PID, workdir, uptime, last output line
  - "Attach" button to view in Stream panel
- **Agent History**: Recent completed sub-agent runs with results

### 5. Periodic Jobs
- **Cron Jobs** table: Name, schedule, next run, last run, status, payload preview
- **Heartbeat**: Current interval, last beat, checks performed
- **Job History**: Recent runs with outcomes (expandable)
- **Visual Timeline**: Gantt-like view of job schedules over 24h

### 6. Live Stream
- **Terminal emulator** (xterm.js) showing real-time output from:
  - Kurtosis devnet runs
  - Coding agent sessions
  - Debug/investigation sessions
- **Tab bar** for multiple streams
- **Session selector** dropdown to pick which process to watch
- **Auto-scroll** with pause on scroll-up
- **Search** within stream output

## Data Flow

### Task Sync (bidirectional)
1. On startup: Parse BACKLOG.md → populate tasks.json (if empty)
2. Dashboard edits → update tasks.json + regenerate BACKLOG.md
3. External BACKLOG.md edits → detect via file watcher → merge into tasks.json
4. Conflict resolution: Dashboard state wins for position/column, BACKLOG.md wins for content

### GitHub Data
- Poll every 60s: `gh pr list`, `gh api notifications`
- Cache in memory, persist to github-cache.json
- Show stale indicator if poll fails

### Discord Data  
- Poll every 120s: Read tracked threads from memory/discord-threads.json
- For each thread: fetch recent messages count/timestamps
- Cache in memory

### Agent Status
- Poll every 10s: `sessions_list`, `process list`
- Push updates via WebSocket

### Token Usage
- Poll every 30s: `session_status` for main session
- Historical data: Append to usage-history.json (daily aggregates)
- Chart: Line graph of tokens/cost over time

## Security Spec

### Authentication Flow
1. First run: Setup wizard prompts for admin username + password
2. Password hashed with bcrypt (cost factor 12)
3. Login returns JWT in httpOnly secure cookie (SameSite=Strict)
4. All API routes require valid JWT (middleware)
5. WebSocket auth: Send JWT as first message after connect

### Invite System
1. Admin generates invite link: `/api/auth/invite` → returns one-time token URL
2. Invitee visits URL, sets username + password
3. Invite tokens expire after 24h, single-use
4. Admin can list/revoke users

### Security Headers
- Content-Security-Policy: strict, no inline scripts
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- Strict-Transport-Security (when behind HTTPS proxy)
- Referrer-Policy: no-referrer

### Rate Limiting
- Auth endpoints: 5 requests/minute per IP
- API endpoints: 100 requests/minute per user
- WebSocket: 50 messages/minute per connection

## File Structure
```
lodekeeper-dash/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── .env.example           # template (no secrets)
├── .gitignore             # includes data/, config.json
├── README.md
├── server/
│   ├── index.ts           # Express + WS entry
│   ├── auth/
│   │   ├── jwt.ts
│   │   ├── passwords.ts
│   │   └── middleware.ts
│   ├── api/
│   │   ├── tasks.ts
│   │   ├── tracking.ts
│   │   ├── agents.ts
│   │   ├── jobs.ts
│   │   ├── status.ts
│   │   └── usage.ts
│   ├── collectors/
│   │   ├── workspace.ts   # BACKLOG.md parser/writer
│   │   ├── github.ts      # gh CLI wrapper
│   │   ├── discord.ts     # thread tracker
│   │   ├── agents.ts      # session/process monitor
│   │   ├── cron.ts        # job list/history
│   │   └── usage.ts       # token tracking
│   ├── ws/
│   │   ├── hub.ts         # WebSocket broadcast
│   │   └── streams.ts     # Terminal stream relay
│   └── storage/
│       └── store.ts       # JSON file read/write
├── src/                   # React frontend
│   ├── main.tsx
│   ├── App.tsx
│   ├── api/
│   │   ├── client.ts      # API client
│   │   └── ws.ts          # WebSocket client
│   ├── components/
│   │   ├── Layout.tsx
│   │   ├── StatusBadge.tsx
│   │   ├── TaskBoard/
│   │   │   ├── Board.tsx
│   │   │   ├── Column.tsx
│   │   │   ├── TaskCard.tsx
│   │   │   └── TaskModal.tsx
│   │   ├── Tracking/
│   │   │   ├── DiscordThreads.tsx
│   │   │   ├── GitHubPRs.tsx
│   │   │   └── GitHubIssues.tsx
│   │   ├── Agents/
│   │   │   ├── SessionCard.tsx
│   │   │   ├── ProcessCard.tsx
│   │   │   └── AgentHistory.tsx
│   │   ├── Jobs/
│   │   │   ├── CronTable.tsx
│   │   │   ├── HeartbeatStatus.tsx
│   │   │   └── JobTimeline.tsx
│   │   ├── Stream/
│   │   │   ├── Terminal.tsx
│   │   │   └── StreamSelector.tsx
│   │   ├── Dashboard/
│   │   │   ├── StatusCard.tsx
│   │   │   ├── TaskSummary.tsx
│   │   │   ├── ActiveAgents.tsx
│   │   │   ├── ActivityFeed.tsx
│   │   │   └── QuickStats.tsx
│   │   └── Auth/
│   │       ├── LoginForm.tsx
│   │       ├── SetupWizard.tsx
│   │       └── InviteAccept.tsx
│   ├── hooks/
│   │   ├── useWebSocket.ts
│   │   ├── useAuth.ts
│   │   └── useTasks.ts
│   ├── stores/             # Zustand stores
│   │   ├── authStore.ts
│   │   ├── taskStore.ts
│   │   └── agentStore.ts
│   └── styles/
│       └── index.css       # Tailwind imports
├── data/                   # gitignored runtime data
│   ├── config.json         # users, hashed passwords
│   ├── tasks.json
│   ├── usage-history.json
│   └── github-cache.json
└── public/
    └── favicon.svg
```

## Implementation Phases

### Phase 1: Foundation (server + auth + basic UI shell)
- Express server with JWT auth
- Login page + setup wizard
- React app shell with sidebar navigation
- Status endpoint reading from workspace

### Phase 2: Task Board
- Task CRUD API
- BACKLOG.md parser/writer (bidirectional sync)
- Kanban UI with drag-and-drop
- WebSocket sync for multi-user edits

### Phase 3: Tracking & Monitoring
- GitHub collector (PRs, issues, notifications via gh CLI)
- Discord thread collector
- Tracking panel UI (tables with expandable rows)

### Phase 4: Agents & Jobs
- Agent/session collector 
- Cron job collector
- Agent cards + job table UI
- Token usage charts

### Phase 5: Live Stream
- WebSocket terminal relay
- xterm.js integration
- Process selector + tab management

### Phase 6: Polish & Security Audit
- UX review with sub-agent
- Security hardening review
- README + deployment docs
- Performance optimization

## Acceptance Criteria
- [ ] Secure login (bcrypt + JWT), no default credentials
- [ ] Kanban board with drag-and-drop, syncs with BACKLOG.md
- [ ] Nico can add/edit/move tasks via UI
- [ ] Discord threads and GitHub PRs visible with links
- [ ] Cron jobs and heartbeat displayed in table
- [ ] Running agents shown with current task
- [ ] Live terminal stream works for background processes
- [ ] Status indicator shows current activity
- [ ] Token usage displayed with chart
- [ ] No private data in git repo
- [ ] Works behind reverse proxy (HTTPS-ready)
- [ ] UX expert approved
- [ ] Security audit passed
