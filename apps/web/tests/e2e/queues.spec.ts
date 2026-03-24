import { expect, test, type APIRequestContext } from '@playwright/test';

async function emitScenario(request: APIRequestContext, payload: Record<string, unknown>): Promise<void> {
  const response = await request.post('http://127.0.0.1:8090/lab/emit', {
    data: payload,
  });
  expect(response.ok()).toBeTruthy();
}

test('queues page switches detail between default and slow', async ({ page, request }) => {
  await emitScenario(request, {
    scenario: 'success',
    count: 1,
    message: 'queues e2e / default',
  });
  await emitScenario(request, {
    scenario: 'slow',
    count: 1,
    delay_seconds: 10,
    message: 'queues e2e / slow',
  });

  await page.goto('/queues');

  await expect(page.getByRole('button', { name: /default/i })).toBeVisible();
  await expect(page.getByRole('button', { name: /slow/i })).toBeVisible();

  const defaultDetail = page.getByLabel('Queue detail: default');
  const slowDetail = page.getByLabel('Queue detail: slow');
  const defaultVisible = await defaultDetail.isVisible().catch(() => false);

  if (defaultVisible) {
    await page.getByRole('button', { name: /slow/i }).click();
    await expect(slowDetail).toBeVisible();
    await page.getByRole('button', { name: /default/i }).click();
    await expect(defaultDetail).toBeVisible();
    return;
  }

  await expect(slowDetail).toBeVisible();
  await page.getByRole('button', { name: /default/i }).click();
  await expect(defaultDetail).toBeVisible();
  await page.getByRole('button', { name: /slow/i }).click();
  await expect(slowDetail).toBeVisible();
});
