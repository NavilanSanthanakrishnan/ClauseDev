import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  use: {
    baseURL: 'http://127.0.0.1:4173',
    trace: 'on-first-retry',
  },
  webServer: [
    {
      command: 'cd backend && uv run clauseai-api',
      port: 8000,
      reuseExistingServer: true,
    },
    {
      command: 'npm --prefix frontend run preview -- --host 127.0.0.1 --port 4173',
      port: 4173,
      reuseExistingServer: true,
    },
  ],
});
