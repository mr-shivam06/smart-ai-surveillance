import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],

  server: {
    port: 5173,
    open: true, // auto-open browser

    proxy: {
      '/auth':     { target: 'http://localhost:8000', changeOrigin: true },
      '/cameras':  { target: 'http://localhost:8000', changeOrigin: true },
      '/tracking': { target: 'http://localhost:8000', changeOrigin: true },
      '/alerts':   { target: 'http://localhost:8000', changeOrigin: true },
      '/vehicles': { target: 'http://localhost:8000', changeOrigin: true },
      '/health':   { target: 'http://localhost:8000', changeOrigin: true },
    }
  }
})