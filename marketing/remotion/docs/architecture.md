# Remotion Architecture

## Purpose

`marketing/remotion` is the foundation for creating many Lux marketing videos
with repeatable project setup and optional reusable building blocks.

## Directory Roles

- `projects/`: each video has its own isolated Remotion project directory.
- `templates/project-base/`: canonical source used to create new projects.
- `packages/video-kit/`: shared primitives that projects may import if useful.
  - terminal visuals: window, scrolling terminal, typing text, cursor.
  - Lux UI visuals: dashboard layout, stats/filter/timeline/runs panels.
- `skills/`: canonical shared skill library for Remotion workflows.
- `scripts/new-video.ts`: scaffolds a new project from template.
- `docs/`: durable guidance for users and agents.

## Core Rules

- A project directory name is the primary identifier.
- New projects are independent by default.
- Reuse from `video-kit` is opt-in.
- Shared Remotion skills are sourced from `skills/`, not per-project copies.
- Legacy projects remain valid references and are not rewritten by default.
