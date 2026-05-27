---
name: add-agent-tool
description: Guided workflow to add a new tool to the DogBuddy agent. Asks for the tool's purpose, arguments, role-gating, and writes a properly-shaped @tool function inside make_tools() with the right audit_log instrumentation. Use this every time the agent needs a new capability.
---

# DogBuddy: Add an Agent Tool

DogBuddy's tools live in `backend/agent/tools.py` inside `make_tools(staff_id)`
so every tool has the calling user's id captured by closure. This skill
walks you through adding one correctly without manually wrangling the
audit-log boilerplate.

## Process

### 1. Interview (one question at a time)

Ask the user — in this order, waiting for each answer:

1. **Purpose** — what should the agent be able to do that it can't today?
2. **Tool name** — short, snake_case, agent-readable (e.g.
   `update_kennel_assignment`).
3. **Arguments** — list each arg as `name: type — description`. Pydantic
   v2 types: `str`, `int`, `float`, `Optional[str]`, etc.
4. **Role-gate** — `staff`-only, `owner`-only, or both? (This is enforced
   by checking the role on the user record we fetch with `staff_id`.)
5. **Mutates state?** — does it change DB rows? If yes, we'll add an
   `audit_log` row with `via='agent'`.
6. **Failure modes** — what should the tool return on (a) missing/wrong
   target, (b) bad args, (c) unexpected exception?

### 2. Show a diff before writing

Before editing `tools.py`, show the user the proposed `@tool` function
including:
- docstring (this is what the LLM reads to decide when to use the tool —
  it MUST be clear and example-rich)
- arg validation
- `with SessionLocal()` block
- audit_log call if mutating
- try/except returning a string (NEVER raise to the agent — see PRD §7
  error-handling)

Wait for explicit confirmation.

### 3. Write

Insert the new `@tool` function inside `make_tools()` in `tools.py`,
between the existing tools (not at the end of the file — `make_tools`
returns a list, so the new tool must also be added to the return statement).

Update the return statement to include the new tool by name.

### 4. Update the system prompt

Tell the user: the agent won't reliably call the new tool unless its
description is also in `backend/agent/prompts/main_system.md`. Add a
bullet under "Tools available" for the appropriate role section
(staff or owner). Keep it one line; the docstring carries the detail.

### 5. Test

Without running it for the user, give them the exact curl or chat
prompt that exercises the new tool, e.g.:
> "Try in chat: *'<example user utterance>'* — the agent should call
> `<tool_name>(<expected args>)`."

If it's a mutating tool, also give the SQL or curl to verify the
state change + the audit_log row.

### 6. Suggest a stress probe

Recommend adding one row to `backend/stress_test.py` that probes a
failure mode of the new tool (wrong arg types, target doesn't exist,
permission boundary). Without this, the next regression run won't
cover the new surface.

## Anti-patterns to avoid

- DON'T put the tool function at module scope. Tools must live inside
  `make_tools()` so `staff_id` is captured by closure.
- DON'T write `raise` inside a tool. The agent can't handle exceptions
  gracefully; return a string starting with `"Error: ..."` instead.
- DON'T forget to add the new tool name to the return list of
  `make_tools` — the agent won't see it otherwise.
- DON'T leave `audit_log` writes out of mutating tools. The audit log
  is the deterministic eval oracle — losing it breaks future evaluators.
- DON'T use numeric examples in the docstring or system prompt when
  it's a safety-sensitive tool. The model will reproduce those numbers.
