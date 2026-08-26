# Dev servers: probe, don't manage

The backend (`uvicorn server:app --port 8000`) and frontend (`vite --port 5173`)
are normally already running in a terminal the user keeps open. Vite's dev
proxy (`frontend/vite.config.ts`) forwards `/api` and `/drills` to a
**hardcoded** `http://127.0.0.1:8000` — it does not discover the backend
dynamically.

**Agents (including subagents and worktree sessions) must only probe these
services (curl, Playwright, etc.) — never start, stop, or restart them.**

If an agent starts its own backend instance (e.g. because it didn't check
whether one was already running, or hit a port conflict), and kills/restarts
the existing process, the new instance won't necessarily land back on
`127.0.0.1:8000`, and Vite's proxy has no way to notice — it just keeps
forwarding to a dead target. The result looks like "the API is broken" when
actually the dev server topology got scrambled by an agent trying to be
helpful.

If a task genuinely needs its own backend/frontend instance (e.g. testing
against different code in a worktree), bind it to a different port instead of
touching the shared one on 8000/5173.
