# Conventions

## Naming

- Use directory-safe project names:
  - lowercase letters
  - digits
  - hyphen (`-`)
  - underscore (`_`)
- Avoid spaces and punctuation in project directory names.

## Project Ownership

- One video project per directory in `projects/`.
- Keep project-specific assets in each project's `public/` directory.
- Place only broadly reusable code in `packages/video-kit/`.
- Place shared Remotion skills in `skills/` as the canonical location.
- Do not create long-lived project-local skill copies unless they are truly
  project-specific.
- Do not move campaign-specific copy, scenes, or assets into `video-kit`.

## Template Discipline

- `templates/project-base/` is the single source for new project scaffolding.
- If scaffold behavior changes, update:
  - `templates/project-base/`
  - `scripts/new-video.ts`
  - scaffold docs

## Skills

- `skills/remotion-best-practices/` is the canonical shared skill directory.
