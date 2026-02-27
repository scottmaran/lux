# Remotion Workspace

This directory contains Lux marketing video projects built with Remotion.

## Layout

- `projects/`: one directory per video project.
- `templates/`: source template used by `new-video`.
- `packages/video-kit/`: shared optional primitives for future reuse.
- `skills/`: shared Remotion skills for users and agents.
- `scripts/`: workspace utilities (currently scaffolding).
- `docs/`: architecture and workflow documentation.

## Quick Start

1. Run `nvm use` in this directory.
2. Install script dependencies:
   - `npm install`
3. Scaffold a new project:
   - `npm run new-video -- --name <project-name>`

## Notes

- New projects are independent by default and are not forced to use `video-kit`.
- Shared skills should be read from `skills/` (canonical location).
- Existing projects in `projects/` may be legacy references.
- `video-kit` currently includes reusable terminal and Lux UI visual primitives.
- See `docs/video-kit.md` for module-level scope and boundaries.
