import { test } from '@playwright/test'

test('check module exports', async ({ page }) => {
  await page.goto('http://localhost:3000')
  
  // Check the actual error in the console
  const errors = await page.evaluate(() => {
    // Try to check what's happening with the imports
    return {
      documentBody: document.body.innerHTML,
      rootElement: document.getElementById('root')?.innerHTML || 'No root element',
      scripts: Array.from(document.scripts).map(s => s.src || s.innerHTML.substring(0, 100))
    }
  })
  
  console.log('Page state:', JSON.stringify(errors, null, 2))
  
  // Get all console messages
  const messages: string[] = []
  page.on('console', msg => {
    messages.push(`${msg.type()}: ${msg.text()}`)
  })
  
  // Wait a bit for any async errors
  await page.waitForTimeout(2000)
  
  console.log('All console messages:', messages)
})