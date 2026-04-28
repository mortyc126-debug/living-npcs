// Stub: prismarine-viewer Camera disabled (no native canvas/gl deps on Windows).
// См. ADR-006 — viewer не нужен.
const silent = new Proxy(() => silent, {
  get: () => silent,
  apply: () => silent,
  construct: () => silent,
});

// Все возможные именованные экспорты, которые могут потребоваться в Mindcraft
export const Camera = silent;
export const Viewer = silent;
export const WorldView = silent;
export const getBufferFromStream = silent;
export const ScreenshotCamera = silent;

export default silent;
