import { expect, test } from '@playwright/test';

test('homepage renders core ClauseAI shell', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('Bring your bill. We bring you to Congress.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Book a Demo' })).toBeVisible();
});

test('signup to project creation flow works', async ({ page }) => {
  const email = `pw-${Date.now()}@example.com`;

  await page.goto('/signup');
  await page.getByLabel('Display name').fill('Playwright User');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill('strong-password-123');
  await page.getByRole('button', { name: 'Create Account' }).click();

  await expect(page.getByText('Resume drafts or start a new legislative workspace.')).toBeVisible();
  await page.getByRole('button', { name: 'Create Project' }).click();

  await expect(page.getByText('Source document')).toBeVisible();
});
