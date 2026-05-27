# DogBuddy

DogBuddy is a **two-mode web app for a dog boarding facility** — a staff
operations dashboard *and* a customer-facing booking app, sharing one
backend, one login, and one AI copilot.

- **Staff mode** (the original PRD scope): an attendant manages 15–30
  dogs at a time. Today's dashboard, dog check-in/check-out, activity
  logging (walks/feeds/meds), incident logging, plus dedicated Health,
  Incidents, and Owners pages.
- **Owner mode** (added in v2): a dog owner self-signs-up, registers
  their dog, and books a stay for when they travel. They see only their
  own dogs and bookings.

Both modes share the same chat interface. The agent serves a
**different tool set per role**, and can delegate to a specialist
sub-agent (`health_advisor`) for medical questions.

The prototype runs entirely on seeded mock data designed to feel real.
Source-of-truth for the original v1 spec is `DogBuddy - Pr.txt` (PRD) and
`DogBuddy - Vi.txt` (Vision); two-mode + sub-agent + workspace pages
landed on top.

## Prerequisites

- **Python 3.11+** (tested on 3.14)
- **Node 20+** (tested on 22)
- An **OpenAI API key** (the agent uses `gpt-4o-mini`)
- A **Parallel.ai Search API key** (optional — without it, `web_search`
  gracefully degrades to no-sources)
- A **LangSmith API key** (optional — for trace inspection + eval
  experiments)

## Backend setup

```bash
cd backend
python -m venv .venv

# Activate (Windows PowerShell)
.venv\Scripts\Activate.ps1
# Activate (macOS/Linux)
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env       # fill in OPENAI_API_KEY + LANGSMITH_API_KEY etc.
python seed.py             # populates dogbuddy.db with 1 staff + 8 dogs + 3 incidents
uvicorn main:app --reload --port 8000
```

The API is at `http://localhost:8000`. Swagger UI at `/docs`.

## Frontend setup

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

UI at `http://localhost:3000`.

## Test logins

### Staff (seeded)

| Field | Value |
| --- | --- |
| Phone | `9999900001` |
| Password | `dogbuddy123` |

The login screen surfaces this in dev mode.

### Owner (self-signup)

Click "**Create an owner account**" on the login screen, fill in any
name / phone / password. New signups are always `role='owner'` (staff
accounts are seeded only — no UI for staff signup).

## Two modes — what each sees

### Staff workspace

| Tab | Route | What's there |
|---|---|---|
| Today | `/dashboard` | Three sections (Checking In / In Care / Checking Out), dog cards with activity timestamps, tap-to-edit |
| Health | `/health` | Vaccination concerns + recent health incidents, per-dog "Ask Health Advisor" button |
| Incidents | `/incidents` | Last 20 incidents with severity + type filters |
| Owners | `/owners` | Directory of owner accounts with dog counts |
| Chat | `/chat` | Multi-agent chat (DogBuddy + Health Advisor) |
| 🔔 Bell | sidebar | Recent activity (audit log: status changes, bookings, incidents) |

### Owner workspace

| Tab | Route | What's there |
|---|---|---|
| My dogs | `/owner/dashboard` | Owner's own dogs + bookings |
| Register dog | `/owner/register-dog` | Form to add a new dog |
| Book a stay | `/owner/book` | Form to book one of their dogs |
| Chat | `/chat` | Same chat surface, owner-flavoured tools |

## What to try in chat

The chat is the most interesting surface. Tools fire visibly as chips.

### Staff prompts
1. *"Who's in today?"* — calls `query_db(todays_bookings)`.
2. *"Any upcoming bookings for Toby?"* — calls
   `query_db(upcoming_bookings, dog_name=Toby)`. Returns owner-created
   bookings staff might not otherwise see yet.
3. *"Mark Rex as checked in"* — calls `update_status`. Refresh the
   Today tab to see Rex move into "In Care".
4. *"My dog ate chocolate, what do I do?"* — delegates to
   **`health_advisor`** via the `task` tool. You'll see a stethoscope
   chip in the chat showing the delegation.
5. *"Charlie skipped breakfast today"* — calls `log_incident`. See the
   bell notification fire afterwards.

### Owner prompts (sign up first)
1. *"Register my dog Toby, a 3-year-old Husky, 22kg"* — calls
   `register_dog`. Toby appears on your `/owner/dashboard`.
2. *"Book Toby from December 20 to December 27"* — calls
   `create_booking`. Booking shows on your dashboard and in staff's
   `upcoming_bookings`.
3. *"What's the best food for a Husky puppy?"* — delegates to
   `health_advisor`.

### Bonus (any mode)
*"What's the safe dose of ibuprofen for a 10kg dog?"* — should refuse
the dose and defer to a vet. This is the medication-safety guardrail.

## Smoke tests

### Agent end-to-end

```bash
cd backend
python test_agent.py
```

5-prompt PRD-acceptance check (read / update / log / web / refusal).

### Stress test (eval scaffolding)

```bash
cd backend
python stress_test.py
```

16 adversarial probes across 6 failure categories (refusal,
hallucination, routing, confirmation, severity, brevity). Each thread
is named `stress_<timestamp>_NN_<category>` so you can group them in
LangSmith.

## LangSmith integration

When `LANGSMITH_TRACING=true` + `LANGSMITH_API_KEY` are set in
`backend/.env`, every agent run + LLM call + tool call + sub-agent
delegation appears in the configured project (default:
`LANGSMITH_PROJECT=dogbuddy`).

## Skills

`.agents/skills/` contains slash-command skills (installed via
`npx skills@latest add mattpocock/skills`) plus three DogBuddy-specific
skills:

- `dogbuddy-reset` — wipe agent memory, re-seed, restart servers
- `dogbuddy-stress` — run the adversarial probe set + triage
- `add-agent-tool` — guided workflow for adding a new agent tool

The same skills are mirrored under `.claude/skills/` so Claude Code
discovers them.

## Known limitations (prototype)

- **Mocked data.** `seed.py` is the source of truth; no real production
  data flow.
- **No real notifications.** No SMS, email, or push. The in-app bell
  reads from the audit_log.
- **No photos, payments, vet integration, password reset, or offline mode.**
- **SQLite locks under concurrent writes** (~3 staff simultaneously is fine).
- **No rate limiting on `/chat`** — easy to burn OpenAI credits in dev.
- **JWT stored in localStorage** (XSS-vulnerable). Acceptable for
  prototype.
- **Agent memory resets per chat session.** Each chat in the sidebar
  has its own `thread_id` and its own LangGraph checkpoint.
- **`test_agent.py` and `stress_test.py` are smoke harnesses**, not
  full coverage.
- **No CI/CD** — local-only.

## Repo layout

```
.
├── DogBuddy - Pr.txt              # original v1 PRD (source of truth for v1 scope)
├── DogBuddy - Vi.txt              # original v1 Vision
├── README.md                      # this file
├── .agents/skills/                # Claude Code skills (Matt Pocock + DogBuddy-specific)
├── backend/
│   ├── main.py                    # FastAPI entry, all REST endpoints
│   ├── db.py                      # SQLAlchemy models (Staff w/ role, Dog w/ owner_user_id)
│   ├── auth.py                    # JWT + bcrypt + require_role helper
│   ├── audit.py                   # write_audit() helper
│   ├── schemas.py                 # Pydantic request/response models
│   ├── seed.py                    # Mock data populator
│   ├── test_agent.py              # 5-prompt agent smoke test
│   ├── stress_test.py             # 16-prompt adversarial probe set
│   ├── evals/                     # space for LangSmith eval scripts
│   ├── agent/
│   │   ├── graph.py               # deepagents setup w/ health_advisor sub-agent
│   │   ├── tools.py               # 6 tools: query_db, update_status, log_incident,
│   │   │                          #          web_search, register_dog, create_booking
│   │   ├── prompts/
│   │   │   ├── main_system.md     # role-aware system prompt
│   │   │   └── health_advisor.md  # sub-agent's safety-strict prompt
│   │   └── skills/
│   │       └── incident_logging.md
│   └── requirements.txt
└── frontend/
    ├── app/
    │   ├── layout.tsx             # Root layout, dark mode, Inter font
    │   ├── page.tsx               # Role-aware redirect
    │   ├── login/page.tsx         # Split-hero login (works for both roles)
    │   ├── signup/page.tsx        # Owner self-signup
    │   ├── dashboard/page.tsx     # Staff: Today
    │   ├── health/page.tsx        # Staff: Health
    │   ├── incidents/page.tsx     # Staff: Incidents
    │   ├── owners/page.tsx        # Staff: Owners directory
    │   ├── chat/page.tsx          # Shared chat (role-aware tools)
    │   └── owner/
    │       ├── dashboard/page.tsx # Owner home
    │       ├── register-dog/page.tsx
    │       └── book/page.tsx
    ├── components/
    │   ├── Sidebar.tsx            # Role-aware nav + chat history
    │   ├── TopNav.tsx             # Mobile top bar
    │   ├── BottomNav.tsx          # Mobile bottom nav
    │   ├── DogCard.tsx
    │   ├── DogDetailModal.tsx
    │   ├── StatsRow.tsx
    │   ├── ChatBox.tsx
    │   ├── ChatMessage.tsx        # Markdown + sub-agent chip
    │   ├── StatusBadge.tsx
    │   ├── AuthGate.tsx           # Role-based route protection
    │   └── Notifications.tsx
    ├── lib/
    │   ├── api.ts                 # Fetch wrapper with JWT
    │   ├── auth.ts                # Token + user in localStorage
    │   ├── types.ts               # Shared TS types
    │   ├── time.ts                # Relative-time formatter
    │   ├── sse.ts                 # SSE parser over fetch ReadableStream
    │   └── chats.ts               # Chat-thread helpers (listChats, threadIdFor)
    ├── tailwind.config.ts         # 9 design tokens (PRD Section 8)
    └── package.json
```

## Style

- Python: `black .` and `ruff check .` (both clean as of last commit).
- TypeScript: `npx prettier --check ...` and `npx next lint` (both clean).
