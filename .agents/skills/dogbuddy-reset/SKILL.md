---
name: dogbuddy-reset
description: Reset DogBuddy to a clean state — wipe agent thread memory, re-seed the SQLite DB, restart uvicorn and next dev. Run before a stress test, before an eval experiment, or whenever the agent is saying "already done" because of stale checkpointer state.
---

# DogBuddy: Reset

Put DogBuddy back to the canonical post-`seed.py` state:
- 1 staff (Anand · `9999900001` / `dogbuddy123`)
- 8 dogs (Rex, Bruno, Charlie, Bella, Max, Luna, Coco, Simba)
- 8 bookings split 1 / 5 / 2 across checking_in / in_care / checking_out
- 3 pre-seeded incidents
- No LangGraph thread memory carrying state across runs

Use this when:
- You're about to run `stress_test.py` or a LangSmith eval and want a known baseline.
- The agent is saying "already done" because of stale thread memory from an earlier session.
- You manually mutated data via the UI and want to undo.

## Process

### 1. Stop running servers
Stop any running `uvicorn main:app` and `next dev` processes. If they were
started as background tasks in this agent, stop them by task ID; otherwise
Ctrl-C in their terminals.

### 2. Wipe agent memory
The LangGraph checkpointer is a separate SQLite file. Delete it AND the
WAL/SHM siblings:

```bash
rm -f backend/agent_memory.db backend/agent_memory.db-shm backend/agent_memory.db-wal
```

Critical for adversarial testing — without this, the agent remembers
decisions from earlier conversations and short-circuits tool calls.

### 3. Re-seed the facility DB
From `backend/`:

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe seed.py
```

Expected last line: `OK Seed complete: 1 staff, 8 dogs, 8 bookings, 3 incidents`.

### 4. Restart backend
```bash
cd backend
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m uvicorn main:app --reload --port 8000 --host 127.0.0.1
```

Verify:
```bash
curl http://127.0.0.1:8000/health
# {"status":"ok"}
```

### 5. Restart frontend (only if it was down)
```bash
cd frontend && npm run dev
```

Verify it's on port 3000:
```bash
curl -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3000/
# 200
```

If Next picks a non-3000 port, kill the orphan node processes holding
3000/3001 first. The CORS allowlist requires port 3000.

### 6. Report
State: "DogBuddy reset. Backend on :8000, frontend on :3000, agent
memory cleared, 8 dogs at their canonical statuses."
