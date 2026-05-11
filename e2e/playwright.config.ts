import { defineConfig } from '@playwright/test'

const databaseUrl = process.env.DATABASE_URL ?? 'postgresql+asyncpg://katalon:katalon@127.0.0.1:5432/katalon'
const redisUrl = process.env.REDIS_URL ?? 'redis://127.0.0.1:6379/0'
const mediaRoot = process.env.MEDIA_ROOT ?? '/tmp/katalon-media'

export default defineConfig({
  testDir: './tests',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://127.0.0.1:4173',
    trace: 'on-first-retry',
  },
  webServer: [
    {
      command: 'python -m alembic -c migrations/alembic.ini upgrade head && python -m uvicorn katalon.main:app --host 127.0.0.1 --port 8000',
      cwd: '../backend',
      url: 'http://127.0.0.1:8000/health',
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
      env: {
        DATABASE_URL: databaseUrl,
        REDIS_URL: redisUrl,
        MEDIA_ROOT: mediaRoot,
      },
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 4173',
      cwd: '../frontend/admin',
      url: 'http://127.0.0.1:4173',
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
      env: {
        VITE_API_URL: 'http://127.0.0.1:8000',
      },
    },
  ],
})
