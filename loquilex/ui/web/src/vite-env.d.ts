/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_WS_PATH: string
  // Add other env variables here
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}