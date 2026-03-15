import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

// API URL: use 'api:8000' in Docker, 'localhost:8000' on host machine
const apiTarget = process.env.API_TARGET || 'http://localhost:8000'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    // Allow non-localhost Host headers (e.g. other Docker services like "web:5173")
    // so tools like Playwright (running in another container) can navigate the dev server.
    // NOTE: Vite blocks unknown hosts by default (DNS rebinding protection).
    allowedHosts: ['localhost', '127.0.0.1', 'web', 'esg-web', 'host.docker.internal'],
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
      // Back-compat for any legacy asset URLs (e.g. "/uploads/...") while we migrate to
      // "/api/v1/assets/{asset_id}/file".
      '/uploads': {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/setupTests.ts'],
    globals: true,
  },
})
