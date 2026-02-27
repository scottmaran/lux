# Asset Reuse Policy

## Default Behavior

New video projects should be independently creatable and should not be forced to
reuse code or assets from previous videos.

## Reuse Is Optional

- Teams may reuse assets or code when it materially helps a video.
- Reuse should be intentional, not automatic.
- `packages/video-kit/` is the preferred place for code primitives that have
  clear cross-project value.

## Practical Guidance

- Keep campaign-specific art/audio in project-local `public/`.
- Promote stable, reusable primitives into `video-kit` only after they prove
  useful in multiple projects.
