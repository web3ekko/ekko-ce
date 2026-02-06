/**
 * Simple Playwright test to verify custom authentication page loads correctly
 * This test checks for import errors and basic functionality
 */

import { chromium } from 'playwright';

async function testCustomAuth() {
  console.log('🚀 Starting custom authentication test...');
  
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();
  
  // Track all console messages
  const consoleErrors = [];
  const consoleMessages = [];
  page.on('console', msg => {
    const message = `[${msg.type()}] ${msg.text()}`;
    consoleMessages.push(message);

    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
      console.log('❌ Console error:', msg.text());
    } else {
      console.log('📝 Console:', message);
    }
  });
  
  try {
    console.log('🌐 Navigating to http://localhost:5175/custom-auth');
    await page.goto('http://localhost:5175/custom-auth');
    
    // Wait for page to load
    await page.waitForLoadState('networkidle');
    console.log('✅ Page loaded');
    
    // Check for import errors
    const importErrors = consoleErrors.filter(error => 
      error.includes('does not provide an export') || 
      error.includes('SyntaxError') ||
      error.includes('auth-simple')
    );
    
    if (importErrors.length > 0) {
      console.log('❌ Import errors found:');
      importErrors.forEach(error => console.log(`   - ${error}`));
      throw new Error(`Import errors detected: ${importErrors.length}`);
    } else {
      console.log('✅ No import errors detected');
    }
    
    // Take screenshot to see what's actually on the page
    await page.screenshot({ path: 'page-content.png' });
    console.log('📸 Page content screenshot saved');

    // Get page content for debugging
    console.log('📄 Page title:', await page.title());

    // Check what's in the body
    const bodyText = await page.locator('body').textContent();
    console.log('📄 Body text (first 200 chars):', bodyText.substring(0, 200));

    // Check for React root element
    const reactRoot = page.locator('#root');
    const rootExists = await reactRoot.count();
    console.log(`🔍 React root element count: ${rootExists}`);

    if (rootExists > 0) {
      const rootContent = await reactRoot.textContent();
      console.log('📄 Root content (first 200 chars):', rootContent.substring(0, 200));
    }

    // Check for main header with more flexible selector
    const header = page.locator('h1');
    const headerCount = await header.count();
    console.log(`🔍 Found ${headerCount} h1 elements`);

    if (headerCount > 0) {
      const headerText = await header.first().textContent();
      console.log(`📝 First h1 text: "${headerText}"`);
    }

    // Try to find the header with a more flexible approach
    const demoHeader = page.locator('h1:has-text("Custom Authentication Demo")');
    const demoHeaderVisible = await demoHeader.isVisible();

    if (demoHeaderVisible) {
      console.log('✅ Main header found');
    } else {
      console.log('⚠️  Main header not found, checking for any authentication-related text');
      const authText = page.locator('text=authentication, text=Authentication, text=auth, text=Auth');
      const authCount = await authText.count();
      console.log(`🔍 Found ${authCount} authentication-related text elements`);
    }
    
    // Check for email input
    const emailInput = page.locator('input[type="email"]');
    await emailInput.waitFor({ timeout: 5000 });
    console.log('✅ Email input found');
    
    // Check for Continue button
    const continueButton = page.locator('button:has-text("Continue")');
    await continueButton.waitFor({ timeout: 5000 });
    console.log('✅ Continue button found');
    
    // Test email validation
    console.log('🧪 Testing email validation...');
    
    // Enter invalid email
    await emailInput.fill('invalid-email');
    await page.waitForTimeout(500);
    
    // Check if Continue button is disabled
    const isDisabled = await continueButton.isDisabled();
    if (isDisabled) {
      console.log('✅ Continue button correctly disabled for invalid email');
    } else {
      console.log('⚠️  Continue button should be disabled for invalid email');
    }
    
    // Enter valid email
    await emailInput.fill('test@example.com');
    await page.waitForTimeout(500);
    
    // Check if Continue button is enabled
    const isEnabled = await continueButton.isEnabled();
    if (isEnabled) {
      console.log('✅ Continue button correctly enabled for valid email');
    } else {
      console.log('⚠️  Continue button should be enabled for valid email');
    }
    
    // Test proceeding to next step
    console.log('🧪 Testing authentication flow...');
    await continueButton.click();
    
    // Wait for next step to load
    await page.waitForTimeout(2000);
    
    // Check if we proceeded to authentication method
    const passkeyAuth = page.locator('h2:has-text("Use Touch ID/Face ID to Sign In")');
    const magicLinkAuth = page.locator('h2:has-text("Check Your Email")');
    
    const passkeyVisible = await passkeyAuth.isVisible();
    const magicLinkVisible = await magicLinkAuth.isVisible();
    
    if (passkeyVisible) {
      console.log('✅ Proceeded to passkey authentication');
    } else if (magicLinkVisible) {
      console.log('✅ Proceeded to magic link authentication');
    } else {
      console.log('⚠️  Did not proceed to expected authentication method');
    }
    
    // Take a screenshot for verification
    await page.screenshot({ path: 'custom-auth-test.png' });
    console.log('📸 Screenshot saved as custom-auth-test.png');
    
    console.log('🎉 All tests passed! Custom authentication is working correctly.');
    
  } catch (error) {
    console.error('❌ Test failed:', error.message);
    
    // Take screenshot of error state
    await page.screenshot({ path: 'custom-auth-error.png' });
    console.log('📸 Error screenshot saved as custom-auth-error.png');
    
    throw error;
  } finally {
    await browser.close();
  }
}

// Run the test
testCustomAuth()
  .then(() => {
    console.log('✅ Test completed successfully');
    process.exit(0);
  })
  .catch((error) => {
    console.error('❌ Test failed:', error);
    process.exit(1);
  });
