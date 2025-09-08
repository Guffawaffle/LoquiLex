// Fallback JSX types to quiet the editor if @types/react isn't installed.
// This is safe to keep; real React types will override it when present.
declare namespace JSX {
  interface IntrinsicElements {
    [elemName: string]: any
  }
}
