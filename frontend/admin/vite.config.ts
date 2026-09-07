import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: process.env.VITE_BASE_PATH ?? '/',
  server: {
    port: 5173,
    host: true,
    allowedHosts: ['.katalon.local'],
    proxy: {
      '/v1': {
        target: process.env.API_PROXY_TARGET || process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
      '/sparql': {
        target: process.env.API_PROXY_TARGET || process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
      '/iiif': {
        target: process.env.CANTALOUPE_PROXY_TARGET || 'http://cantaloupe:8182',
        changeOrigin: true,
      },
    },
  },
})
