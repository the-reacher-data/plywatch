import { expect, test, type APIRequestContext } from '@playwright/test';

async function emitScenario(request: APIRequestContext, payload: Record<string, unknown>): Promise<void> {
  const response = await request.post('http://127.0.0.1:8090/lab/emit', {
    data: payload,
  });
  expect(response.ok()).toBeTruthy();
}

test('queues page switches from active slow queue to default detail', async ({ page, request }) => {
  await emitScenario(request, {
    scenario: 'success',
    count: 2,
    message: 'queues active switch / default',
  });
  await emitScenario(request, {
    scenario: 'slow',
    count: 2,
    delay_seconds: 35,
    message: 'queues active switch / slow',
  });

  await page.goto('/queues?queue=default');

  const defaultButton = page.getByRole('button', { name: /default/i });
  const slowButton = page.getByRole('button', { name: /slow/i });

  await expect(defaultButton).toBeVisible();
  await expect(slowButton).toBeVisible();
  await expect(page.getByLabel('Queue detail: default')).toBeVisible();

  await slowButton.click();
  await expect(page.getByLabel('Queue detail: slow')).toBeVisible();

  await defaultButton.click();
  await expect(page.getByLabel('Queue detail: default')).toBeVisible();
});

test('queues page switches from explicit slow detail to default detail', async ({ page, request }) => {
  await emitScenario(request, {
    scenario: 'success',
    count: 1,
    message: 'queues active switch / default explicit slow',
  });
  await emitScenario(request, {
    scenario: 'slow',
    count: 1,
    delay_seconds: 25,
    message: 'queues active switch / slow explicit slow',
  });

  await page.goto('/queues?queue=slow');

  const defaultButton = page.getByRole('button', { name: /default/i });
  await expect(page.getByLabel('Queue detail: slow')).toBeVisible();
  await defaultButton.click();
  await expect(page.getByLabel('Queue detail: default')).toBeVisible();
});
