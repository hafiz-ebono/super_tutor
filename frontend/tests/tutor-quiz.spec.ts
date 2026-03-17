import { test, expect } from '@playwright/test';
import path from 'path';
import fs from 'fs';

/**
 * Tutor Quiz Mode — Playwright E2E
 *
 * Assumes:
 *   - `next dev` running at http://localhost:3000
 *   - Backend running at http://localhost:8000
 *   - PLAYWRIGHT_E2E env var set (otherwise test is skipped)
 *
 * Run: PLAYWRIGHT_E2E=1 npx playwright test tests/tutor-quiz.spec.ts
 */

const SKIP = !process.env.PLAYWRIGHT_E2E;

test.describe('Tutor Quiz Mode', () => {
  test.skip(SKIP, 'PLAYWRIGHT_E2E not set — skipping live browser test');

  test('quiz me flow delivers MCQ and evaluates answer', async ({ page }) => {
    // 1. Navigate to home page
    await page.goto('/');
    await expect(page).toHaveTitle(/Super Tutor/i, { timeout: 10_000 });

    // 2. Select Topic tab and submit
    await page.getByRole('button', { name: /topic/i }).click();
    await page.getByPlaceholder(/topic/i).fill('photosynthesis — how plants convert light into energy');

    // Select Micro Learning tutoring type if selector is present
    const learningSelect = page.locator('select, [data-testid="tutoring-type"]').first();
    if (await learningSelect.count() > 0) {
      await learningSelect.selectOption({ label: /micro/i });
    }

    await page.getByRole('button', { name: /generate|start|create/i }).click();

    // 3. Wait for study page to load (notes tab visible)
    await expect(page.getByText(/notes/i)).toBeVisible({ timeout: 90_000 });

    // 4. Click Personal Tutor tab
    await page.getByRole('button', { name: /personal tutor|tutor/i }).click();

    // 5. Wait for intro message (streaming — allow up to 30s)
    await expect(page.locator('[data-testid="tutor-chat"], .tutor-chat, #tutor-panel').first())
      .toContainText(/hello|welcome|i can/i, { timeout: 30_000 });

    // 6. Type "quiz me" and send
    const input = page.getByPlaceholder(/ask|message|type/i).last();
    await input.fill('quiz me');
    await page.getByRole('button', { name: /send/i }).last().click();

    // 7. Wait for MCQ response (A/B/C/D present)
    const chatArea = page.locator('[data-testid="tutor-chat"], .tutor-chat, #tutor-panel').first();
    await expect(chatArea).toContainText(/[A-D]\)/i, { timeout: 30_000 });

    // 8. Type "A" and send
    await input.fill('A');
    await page.getByRole('button', { name: /send/i }).last().click();

    // 9. Wait for evaluation response
    await expect(chatArea).toContainText(/correct|answer/i, { timeout: 30_000 });

    // 10. Screenshot final state
    const screenshotDir = path.join(__dirname, '../playwright-screenshots');
    fs.mkdirSync(screenshotDir, { recursive: true });
    await page.screenshot({ path: path.join(screenshotDir, 'tutor-quiz-final.png'), fullPage: true });
  });
});
