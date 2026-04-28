// Stub: prismarine-viewer disabled (no native canvas/gl deps on Windows).
// См. ADR-006 — viewer не нужен, мы наблюдаем Странника через game client.
// Proxy-заглушка: любой метод/свойство возвращает себя, не падает на вызовах.
const silent = new Proxy(() => silent, {
  get: () => silent,
  apply: () => silent,
  construct: () => silent,
});

export default silent;
