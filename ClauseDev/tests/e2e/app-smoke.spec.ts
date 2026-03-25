import { expect, test } from '@playwright/test';

test('homepage renders core ClauseAI shell', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('Bring your bill. We bring you to Congress.')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Book a Demo' })).toBeVisible();
});

test('signup to project creation flow works', async ({ page }) => {
  const email = `pw-${Date.now()}@example.com`;

  await page.goto('/signup');
  await page.getByLabel('Display name').fill('Playwright User');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill('strong-password-123');
  await page.getByRole('button', { name: 'Create Account' }).click();

  await expect(page.getByRole('heading', { name: 'Create a bill workspace or jump back into one.' })).toBeVisible();
  await page.getByRole('button', { name: 'Create workspace' }).click();

  await expect(page.getByRole('heading', { name: 'Upload your bill' })).toBeVisible();
});
