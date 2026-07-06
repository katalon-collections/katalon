import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',
    trace: 'on-first-retry',
  },
  webServer: [
    {
      command: 'docker compose up -d api',
      cwd: '..',
      url: 'http://localhost:8000/health',
      timeout: 120_000,
      reuseExistingServer: true,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5173',
      cwd: '../frontend/admin',
      url: 'http://127.0.0.1:5173',
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
    },
  ],
})
