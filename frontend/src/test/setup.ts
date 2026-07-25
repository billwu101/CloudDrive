import '@testing-library/jest-dom/vitest'

// Node's experimental Web Storage (surfaced by the `--localstorage-file`
// warning on this machine) shadows jsdom's and lacks a working
// clear/removeItem. Install a complete in-memory Storage so upload-resume
// persistence behaves as it does in a browser.
if (typeof localStorage === 'undefined' || typeof localStorage.removeItem !== 'function') {
  const store = new Map<string, string>()
  const memoryStorage: Storage = {
    get length() {
      return store.size
    },
    clear: () => store.clear(),
    getItem: (key: string) => (store.has(key) ? (store.get(key) as string) : null),
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    removeItem: (key: string) => void store.delete(key),
    setItem: (key: string, value: string) => void store.set(key, String(value)),
  }
  Object.defineProperty(globalThis, 'localStorage', {
    value: memoryStorage,
    configurable: true,
    writable: true,
  })
}
