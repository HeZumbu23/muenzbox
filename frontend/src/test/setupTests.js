import '@testing-library/jest-dom'

if (!globalThis.AbortSignal?.timeout) {
  globalThis.AbortSignal = {
    ...globalThis.AbortSignal,
    timeout: () => undefined,
  }
}
