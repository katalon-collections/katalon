/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import type { Plugin } from 'vite'

// The theme stylesheet (tokens + theme CSS, rendered by the API) is linked
// render-blocking at the end of <head> — after the app CSS, so theme rules win
// ties — and the first paint already carries the theme instead of the defaults.
function themeStylesheet(): Plugin {
  return {
    name: 'katalon-theme-stylesheet',
    transformIndexHtml: {
      order: 'post',
      handler: () => [{ tag: 'link', attrs: { rel: 'stylesheet', href: '/portal/v1/theme.css' }, injectTo: 'head' }],
    },
  }
}

export default defineConfig({
  plugins: [react(), themeStylesheet()],
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
