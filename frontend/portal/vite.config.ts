/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
  },
  server: {
    port: 5174,
    host: true,
    allowedHosts: ['.katalon.local'],
    proxy: {
      '/portal/v1': { target: process.env.API_PROXY_TARGET || process.env.VITE_API_URL || 'http://localhost:8000', changeOrigin: true },
      '/v1': { target: process.env.API_PROXY_TARGET || process.env.VITE_API_URL || 'http://localhost:8000', changeOrigin: true },
      '/iiif': { target: process.env.CANTALOUPE_PROXY_TARGET || 'http://cantaloupe:8182', changeOrigin: true },
    },
  },
})
