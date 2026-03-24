import { expect, test } from '@playwright/test';

test('overview page renders', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('Monitor Overview')).toBeVisible();
});
