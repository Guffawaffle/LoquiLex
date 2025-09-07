import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/models': 'http://localhost:8000',
      '/sessions': 'http://localhost:8000',
      '/languages': 'http://localhost:8000'
    }
  }
})
