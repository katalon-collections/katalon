import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      '/portal/v1': { target: process.env.API_PROXY_TARGET || process.env.VITE_API_URL || 'http://localhost:8000', changeOrigin: true },
      '/v1': { target: process.env.API_PROXY_TARGET || process.env.VITE_API_URL || 'http://localhost:8000', changeOrigin: true },
    },
  },
})
