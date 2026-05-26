# DogBuddy

DogBuddy is a staff-only web app for dog boarding facilities. A staff member logs in, sees every dog in the facility today on a three-section dashboard (Checking In / In Care / Checking Out), and talks to an AI copilot — also called DogBuddy — that can read facility data, update statuses, log incidents, and research dog health on the live web. The prototype runs entirely on seeded mock data designed to feel real. Source of truth for behavior is `DogBuddy - Pr.txt` (PRD); product intent is in `DogBuddy - Vi.txt` (Vision).

## Prerequisites

- **Python 3.11+** (tested on 3.14)
- **Node 20+** (tested on 22)
- An **OpenAI API key** (the agent uses `gpt-4o-mini`)
- A **Parallel.ai Search API key** (for the `web_search` tool — optional; without it the agent gracefully falls back without citations)

## Backend setup

```bash
cd backend
python -m venv .venv

# Activate (Windows PowerShell)
.venv\Scripts\Activate.ps1
# Activate (macOS/Linux)
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env       # then fill in OPENAI_API_KEY and PARALLEL_API_KEY
python seed.py             # populates dogbuddy.db with 1 staff + 8 dogs + 3 incidents
uvicorn main:app --reload --port 8000
```

The API will be live at `http://localhost:8000`. Visit `http://localhost:8000/docs` for the Swagger UI.

## Frontend setup

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

The UI will be live at `http://localhost:3000`.

## Test login

| Field | Value |
| --- | --- |
| Phone | `9999900001` |
| Password | `dogbuddy123` |

The login screen also surfaces this hint when running in dev.

## What to try in chat

Once you're logged in, open the **Chat** tab and try these. Each exercises a different agent capability and shows tool chips in the stream:

1. **"Who's in today?"** — should call `query_db` and reply with the 8 dogs grouped by status.
2. **"Mark Rex as checked in"** — should call `update_status`. Switch back to the **Dashboard** tab and Rex will have moved from "Checking In Today" into "In Care".
3. **"Symptoms of heatstroke in dogs?"** — should call `web_search` and reply with a synthesized answer + a `Sources:` list. (If your Parallel key is unset or invalid, the agent will reply from training knowledge without sources.)

Bonus prompt — **"What is the safe dose of ibuprofen for a 10kg dog?"** — should refuse the dose and say "consult your facility vet" per the safety guardrail in `agent/skills/medication_safety.md`.

## Smoke test (backend)

With the backend running, you can verify the agent end-to-end:

```bash
cd backend
python test_agent.py
```

This fires the 5 PRD-acceptance prompts (read / update / log / web / refusal) and prints which tool fired for each plus the final answer, then dumps the `audit_log` table to prove the agent's mutations were recorded.

## Known limitations (prototype)

Acceptable for v1, accepted in `DogBuddy - Vi.txt` Section 7 and `DogBuddy - Pr.txt` Section 13:

- **Single facility, staff-only.** No owner-facing app, no multi-facility logic, no role hierarchy beyond "staff".
- **Mocked data.** No real bookings flow; the dataset is whatever `seed.py` populates.
- **No real notifications.** No SMS, email, or push to owners.
- **No photos, payments, vet integration, password reset, or offline mode.**
- **SQLite locks under concurrent writes** (~3 staff simultaneously is fine).
- **No rate limiting on `/chat`** — easy to burn OpenAI credits in dev; be mindful.
- **JWT stored in localStorage** (XSS-vulnerable). Acceptable for prototype, change for prod.
- **Web search has no caching** — every research query hits Parallel AI.
- **Agent memory resets daily** (intentional simplicity — thread_id encodes the date).
- **No automated test suite** — `test_agent.py` is a smoke harness, not full coverage.
- **No CI/CD** — local-only.

## Repo layout

```
.
├── DogBuddy - Pr.txt          # PRD (source of truth)
├── DogBuddy - Vi.txt          # Vision
├── README.md
├── backend/
│   ├── main.py                # FastAPI entry, all endpoints
│   ├── db.py                  # SQLAlchemy models + session
│   ├── auth.py                # JWT + bcrypt
│   ├── audit.py               # write_audit() helper
│   ├── schemas.py             # Pydantic request/response models
│   ├── seed.py                # Mock data populator
│   ├── test_agent.py          # 5-prompt agent smoke test
│   ├── agent/
│   │   ├── graph.py           # deepagents setup + invoke
│   │   ├── tools.py           # 4 tools: query_db, update_status,
│   │   │                      #          log_incident, web_search
│   │   ├── prompts/main_system.md
│   │   └── skills/
│   │       ├── medication_safety.md
│   │       └── incident_logging.md
│   └── requirements.txt
└── frontend/
    ├── app/
    │   ├── layout.tsx         # Root layout, dark mode, Inter font
    │   ├── page.tsx           # Redirects to /dashboard or /login
    │   ├── login/page.tsx
    │   ├── dashboard/page.tsx
    │   └── chat/page.tsx
    ├── components/
    │   ├── DogCard.tsx
    │   ├── DogDetailModal.tsx
    │   ├── ChatBox.tsx
    │   ├── ChatMessage.tsx
    │   ├── BottomNav.tsx
    │   ├── StatusBadge.tsx
    │   └── AuthGate.tsx
    ├── lib/
    │   ├── api.ts             # Fetch wrapper with JWT
    │   ├── auth.ts            # Token + user in localStorage
    │   ├── types.ts           # Shared TS types
    │   ├── time.ts            # Relative-time formatter
    │   └── sse.ts             # SSE parser over fetch ReadableStream
    ├── tailwind.config.ts     # 9 design tokens from PRD Section 8
    └── package.json
```

## Style

- Python: `black .` and `ruff check .` (both clean as of last commit).
- TypeScript: `npx prettier --check ...` and `npx next lint` (both clean).
