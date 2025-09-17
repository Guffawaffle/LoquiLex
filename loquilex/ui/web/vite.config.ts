import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
declare const process: any

// https://vitejs.dev/config/
export default defineConfig(() => {
  const wsPath = process.env.VITE_WS_PATH || '/ws'
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: Object.assign(
        {
          '/models': { target: 'http://localhost:8000', changeOrigin: true },
          '/sessions': { target: 'http://localhost:8000', changeOrigin: true },
          '/profiles': { target: 'http://localhost:8000', changeOrigin: true },
          '/languages': { target: 'http://localhost:8000', changeOrigin: true },
          '/out': { target: 'http://localhost:8000', changeOrigin: true },
        },
        // Dynamically add WS alias proxy entry
        {
          [wsPath]: { target: 'http://localhost:8000', changeOrigin: true, ws: true },
        }
      ),
    },
  }
})
