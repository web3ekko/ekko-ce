import { test, expect } from '@playwright/test'

test.describe('Dashboard Rendering', () => {
  test('should load the dashboard without errors', async ({ page }) => {
    // Capture console errors
    const consoleErrors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text())
      }
    })

    // Navigate to the dashboard
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle' })

    // Check for any console errors
    console.log('Console errors:', consoleErrors)
    
    // Filter out known non-critical errors
    const criticalErrors = consoleErrors.filter(error => 
      !error.includes('ethereum') && // Browser extension error
      !error.includes('injected-session') && // Browser extension error
      !error.includes('Could not establish connection') // Browser extension error
    )

    // Check for WebSocket export error
    const websocketExportError = consoleErrors.find(error => 
      error.includes('ConnectionState') || 
      error.includes('does not provide an export')
    )

    if (websocketExportError) {
      console.error('WebSocket export error found:', websocketExportError)
    }

    // Take a screenshot for debugging
    await page.screenshot({ path: 'dashboard-error.png', fullPage: true })

    // Check if the root element exists
    const rootElement = await page.$('#root')
    expect(rootElement).not.toBeNull()

    // Check if there's any content rendered
    const rootContent = await page.$eval('#root', el => el.innerHTML)
    console.log('Root element content length:', rootContent.length)

    // Expect no critical errors
    expect(websocketExportError).toBeUndefined()
    expect(criticalErrors).toHaveLength(0)
  })
})