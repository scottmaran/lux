export const FPS = 60;
export const WIDTH = 1920;
export const HEIGHT = 1080;

export const SCENE_FRAMES = {
  intro: 180,
  chaos: 475,
  overlay: 110,
  sceneTransition: 180,
  dashboard: 360,
  // differentiator: 180,
  brand: 200,
} as const;

export const TOTAL_FRAMES =
  SCENE_FRAMES.intro +
  SCENE_FRAMES.chaos +
  SCENE_FRAMES.overlay +
  SCENE_FRAMES.sceneTransition +
  SCENE_FRAMES.dashboard +
  // SCENE_FRAMES.differentiator +
  SCENE_FRAMES.brand;
