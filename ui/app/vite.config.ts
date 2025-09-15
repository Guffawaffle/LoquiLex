import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: parseInt(process.env.LX_UI_PORT || '5173'),
    host: '127.0.0.1',
    proxy: {
      // Proxy API and WebSocket endpoints to FastAPI server
      '/api': {
        target: `http://127.0.0.1:${process.env.LX_API_PORT || '8000'}`,
        changeOrigin: true,
      },
      '/ws': {
        target: `http://127.0.0.1:${process.env.LX_API_PORT || '8000'}`,
        ws: true,
        changeOrigin: true,
      },
      '/models': {
        target: `http://127.0.0.1:${process.env.LX_API_PORT || '8000'}`,
        changeOrigin: true,
      },
      '/sessions': {
        target: `http://127.0.0.1:${process.env.LX_API_PORT || '8000'}`,
        changeOrigin: true,
      },
      '/profiles': {
        target: `http://127.0.0.1:${process.env.LX_API_PORT || '8000'}`,
        changeOrigin: true,
      },
      '/healthz': {
        target: `http://127.0.0.1:${process.env.LX_API_PORT || '8000'}`,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
})