import { test, expect } from '@playwright/test'

test('check module loading', async ({ page }) => {
  // Track network requests
  const moduleRequests: string[] = []
  const failedRequests: string[] = []
  
  page.on('request', request => {
    if (request.url().includes('.ts') || request.url().includes('.tsx')) {
      moduleRequests.push(request.url())
    }
  })
  
  page.on('requestfailed', request => {
    failedRequests.push(`${request.url()} - ${request.failure()?.errorText}`)
  })
  
  // Track console errors
  const consoleErrors: any[] = []
  page.on('console', msg => {
    if (msg.type() === 'error') {
      consoleErrors.push({
        text: msg.text(),
        location: msg.location()
      })
    }
  })
  
  // Enable detailed error tracking
  page.on('pageerror', error => {
    console.log('Page error:', error.message)
    console.log('Stack:', error.stack)
  })
  
  await page.goto('http://localhost:3000', { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(3000) // Wait for modules to load
  
  console.log('Module requests:', moduleRequests.slice(0, 10))
  console.log('Failed requests:', failedRequests)
  console.log('Console errors:', consoleErrors)
  
  // Check specific modules
  const websocketModule = moduleRequests.find(r => r.includes('websocket.ts'))
  console.log('WebSocket module:', websocketModule)
  
  // Try to check if React is loaded
  const reactLoaded = await page.evaluate(() => {
    return typeof window !== 'undefined' && (window as any).React !== undefined
  })
  console.log('React loaded:', reactLoaded)
  
  // Check for syntax errors
  const syntaxError = consoleErrors.find(e => 
    e.text.includes('SyntaxError') || 
    e.text.includes('export')
  )
  
  if (syntaxError) {
    console.error('Syntax error found:', syntaxError)
  }
})