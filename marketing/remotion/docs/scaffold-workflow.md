# Scaffold Workflow

## Prerequisites

1. Open a shell in `marketing/remotion`.
2. Run `nvm use`.
3. Install workspace script dependencies:
   - `npm install`

## Create A New Video Project

Run:

```sh
npm run new-video -- --name <project-name>
```

Example:

```sh
npm run new-video -- --name launch_story_01
```

This creates:

```text
projects/<project-name>/
```

from:

```text
templates/project-base/
```

## Next Steps In The New Project

1. `cd projects/<project-name>`
2. `npm install`
3. `npm run dev`
4. Read shared Remotion guidance from:
   - `skills/remotion-best-practices/SKILL.md`
