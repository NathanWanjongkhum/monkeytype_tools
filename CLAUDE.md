# Guidelines

## Working in Parallel

Agents work in an isolated worktree. When a task is complete: commit to the task branch, then write a brief (<200 words) summary of task, challenges, and decisions.

Integration into `main` happens separately, from the primary checkout, by a single integrator after a diff review. If subagents run in parallel, each produces its own branch; conflicts are resolved once at integration time.

## Dev servers: probe, don't manage

The backend and frontend are normally already running in a terminal the user keeps open. Vite's dev
proxy forwards services to a hardcoded local port it does not discover the backend
dynamically.

| Service  | Command                          |
| -------- | -------------------------------- |
| backend  | `uvicorn server:app --port 8000` |
| frontend | `vite --port 5173`               |
| local    | `http://127.0.0.1:8000`          |

Agents (including subagents and worktree sessions) must only probe these
services (curl, Playwright, etc.) — never start, stop, or restart them.

If a task needs its own instance (e.g. testing against different code in a worktree), bind it to a different port instead of touching the shared one.
