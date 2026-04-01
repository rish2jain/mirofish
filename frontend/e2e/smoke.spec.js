import { test, expect } from '@playwright/test'

test.describe('smoke', () => {
  test('home page loads and shows title', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveTitle(/MiroFish/i)
    await expect(page.locator('body')).toBeVisible()
  })

  test('workflow tools page loads', async ({ page }) => {
    await page.goto('/tools')
    await expect(page.getByRole('heading', { name: /workflow tools/i })).toBeVisible()
  })

  test('report compare page loads', async ({ page }) => {
    await page.goto('/report/compare')
    await expect(page.getByRole('heading', { name: /compare reports/i })).toBeVisible()
  })

  test('simulation compare page loads', async ({ page }) => {
    await page.goto('/simulation/compare')
    await expect(page.getByRole('heading', { name: /compare simulations/i })).toBeVisible()
  })

  test('template editor page loads', async ({ page }) => {
    await page.goto('/templates/edit')
    await expect(page.getByRole('heading', { name: /template editor/i })).toBeVisible()
  })
})
