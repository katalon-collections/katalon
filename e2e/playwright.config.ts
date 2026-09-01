// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { defineConfig } from '@playwright/test'

const isCI = Boolean(process.env.CI)

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
      command: isCI
        ? 'alembic -c migrations/alembic.ini upgrade head && DEBUG=true python -m uvicorn katalon.main:app --host 127.0.0.1 --port 8000'
        : 'docker compose -f docker-compose.yml -f docker-compose.dev.yml up api',
      cwd: isCI ? '../backend' : '..',
      url: 'http://localhost:8000/api/openapi.json',
      timeout: 120_000,
      reuseExistingServer: !isCI,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5173',
      cwd: '../frontend/admin',
      url: 'http://127.0.0.1:5173',
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5174',
      cwd: '../frontend/portal',
      url: 'http://127.0.0.1:5174',
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
    },
  ],
})
