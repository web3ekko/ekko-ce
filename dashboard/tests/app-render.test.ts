import { test, expect } from '@playwright/test'

test.describe('App Rendering', () => {
  test('should render login page by default', async ({ page }) => {
    // Go to the app
    await page.goto('http://localhost:3000')
    
    // Wait for navigation
    await page.waitForURL('**/auth/login', { timeout: 5000 })
    
    // Check if login page elements are visible
    const loginForm = await page.waitForSelector('form', { timeout: 5000 })
    expect(loginForm).toBeTruthy()
    
    // Check for login page text
    const pageContent = await page.textContent('body')
    expect(pageContent).toContain('Sign')
    
    // Take a screenshot
    await page.screenshot({ path: 'login-page.png', fullPage: true })
    
    console.log('Login page rendered successfully')
  })
  
  test('should have no critical console errors', async ({ page }) => {
    const criticalErrors: string[] = []
    
    page.on('console', msg => {
      if (msg.type() === 'error') {
        const text = msg.text()
        // Filter out known browser extension errors
        if (!text.includes('ethereum') && 
            !text.includes('injected-session') && 
            !text.includes('Could not establish connection')) {
          criticalErrors.push(text)
        }
      }
    })
    
    await page.goto('http://localhost:3000')
    await page.waitForTimeout(2000)
    
    console.log('Critical errors found:', criticalErrors)
    expect(criticalErrors).toHaveLength(0)
  })
})