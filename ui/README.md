
  # Agent Harness UI (Redesign)

  This UI is a React + Vite build served by the local Python API server.

  ## Development

  Install dependencies:

  ```bash
  npm install
  ```

  Run the Vite dev server:

  ```bash
  npm run dev
  ```

  ## Production (container)

  The `ui/Dockerfile` builds the Vite app and serves it with `ui/server.py`.
  The server also exposes the local-only API under `/api/*` for timeline and runs.
  
