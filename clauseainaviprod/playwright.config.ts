import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/playwright',
  timeout: 120_000,
  reporter: [['list'], ['json', { outputFile: 'artifacts/qa/playwright-results.json' }]],
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
  },
});
