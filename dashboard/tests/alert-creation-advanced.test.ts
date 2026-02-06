import { test, expect } from '@playwright/test'

test.describe('Alert Creation with Advanced Options', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the dashboard (assuming demo mode is enabled)
    await page.goto('http://localhost:3000/dashboard/alerts')
    
    // Wait for the page to load
    await page.waitForSelector('text=Alerts', { timeout: 10000 })
  })

  test('should display instance settings in alert creation form', async ({ page }) => {
    // Click on Create Alert button
    await page.click('button:has-text("Create Alert")')
    
    // Wait for modal to open
    await page.waitForSelector('text=Create New Alert', { timeout: 5000 })

    await expect(page.locator('text=Save Template')).toBeVisible()
    await expect(page.locator('text=Alert Instance Settings')).toBeVisible()
    await page.getByLabel('Toggle alert instance settings').click()
    await expect(page.locator('text=Target Selection')).toBeVisible()
    await expect(page.locator('text=Trigger Type')).toBeVisible()
  })

  test('should disable create until template is saved', async ({ page }) => {
    // Click on Create Alert button
    await page.click('button:has-text("Create Alert")')
    
    // Wait for modal to open
    await page.waitForSelector('text=Create New Alert')

    const createButton = page.locator('button:has-text("Create Alert"):visible')
    await expect(createButton).toBeDisabled()
  })

  test('should display progress indicator after typing', async ({ page }) => {
    // Click on Create Alert button
    await page.click('button:has-text("Create Alert")')
    
    // Wait for modal to open
    await page.waitForSelector('text=Create New Alert')

    await page.fill('textarea', 'Alert me when BTC price crosses $45,000')

    await expect(page.locator('text=Analyzing')).toBeVisible()
  })
})
