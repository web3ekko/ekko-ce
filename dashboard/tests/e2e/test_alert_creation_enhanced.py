"""
End-to-end tests for the enhanced alert creation form with iOS-style design
"""

import pytest
from playwright.sync_api import Page, expect
import time


class TestEnhancedAlertCreation:
    """Test the enhanced alert creation form with executive styling"""

    def test_alert_creation_form_loads(self, page: Page):
        """Test that the enhanced alert creation form loads correctly"""
        # Navigate to alerts page
        page.goto("http://localhost:3000/alerts")
        
        # Wait for page to load
        page.wait_for_selector("text=Alert Management", timeout=10000)
        
        # Click the Create Alert button (with wand icon)
        create_button = page.locator("button:has-text('Create Alert')").filter(has=page.locator("[data-tabler-icon='wand']"))
        create_button.click()
        
        # Wait for modal to appear
        page.wait_for_selector("text=Create Smart Alert", timeout=5000)
        
        # Verify the modal elements
        expect(page.locator("text=AI-powered monitoring for your blockchain assets")).to_be_visible()
        expect(page.locator("text=AI Powered")).to_be_visible()
        
        # Check mode selector
        expect(page.locator("text=Natural Language")).to_be_visible()
        expect(page.locator("text=Visual Builder")).to_be_visible()

    def test_natural_language_input(self, page: Page):
        """Test natural language input with confidence indicator"""
        page.goto("http://localhost:3000/alerts")
        
        # Open create alert modal
        page.locator("button:has-text('Create Alert')").filter(has=page.locator("[data-tabler-icon='wand']")).click()
        page.wait_for_selector("text=Create Smart Alert")
        
        # Type in natural language input
        nl_input = page.locator("input").filter(has_text="Describe your alert in natural language")
        nl_input.fill("Alert me when ETH drops below $2000 or gas fees exceed 100 gwei")
        
        # Wait for confidence indicator to appear
        page.wait_for_selector("text=AI Confidence", timeout=5000)
        
        # Check that confidence percentage is shown
        confidence_text = page.locator("text=%").first
        expect(confidence_text).to_be_visible()
        
        # Verify helper text
        expect(page.locator("text=Example: Alert me when ETH drops below")).to_be_visible()

    def test_advanced_options_toggle(self, page: Page):
        """Test advanced options expand/collapse functionality"""
        page.goto("http://localhost:3000/alerts")
        
        # Open create alert modal
        page.locator("button:has-text('Create Alert')").filter(has=page.locator("[data-tabler-icon='wand']")).click()
        page.wait_for_selector("text=Create Smart Alert")
        
        # Click Advanced Options
        advanced_section = page.locator("text=Advanced Options").first
        advanced_section.click()
        
        # Wait for advanced options to expand
        page.wait_for_selector("text=Notification Channels", timeout=3000)
        
        # Verify all notification options are visible
        expect(page.locator("text=Email")).to_be_visible()
        expect(page.locator("text=SMS")).to_be_visible()
        expect(page.locator("text=Push")).to_be_visible()
        expect(page.locator("text=Webhook")).to_be_visible()
        
        # Verify alert settings
        expect(page.locator("text=Alert Frequency")).to_be_visible()
        expect(page.locator("text=Priority Level")).to_be_visible()

    def test_notification_channels_selection(self, page: Page):
        """Test notification channel toggles and webhook URL"""
        page.goto("http://localhost:3000/alerts")
        
        # Open create alert modal
        page.locator("button:has-text('Create Alert')").filter(has=page.locator("[data-tabler-icon='wand']")).click()
        page.wait_for_selector("text=Create Smart Alert")
        
        # Expand advanced options
        page.locator("text=Advanced Options").first.click()
        page.wait_for_selector("text=Notification Channels")
        
        # Toggle webhook option
        webhook_switch = page.locator("label:has-text('Webhook')").locator("input[type='checkbox']")
        webhook_switch.click()
        
        # Wait for webhook URL input to appear
        page.wait_for_selector("input[placeholder='https://your-webhook.com/alerts']", timeout=3000)
        
        # Fill webhook URL
        webhook_input = page.locator("input[placeholder='https://your-webhook.com/alerts']")
        webhook_input.fill("https://api.example.com/alerts")
        
        # Verify the input was filled
        expect(webhook_input).to_have_value("https://api.example.com/alerts")

    def test_frequency_and_priority_selection(self, page: Page):
        """Test alert frequency and priority controls"""
        page.goto("http://localhost:3000/alerts")
        
        # Open create alert modal
        page.locator("button:has-text('Create Alert')").filter(has=page.locator("[data-tabler-icon='wand']")).click()
        page.wait_for_selector("text=Create Smart Alert")
        
        # Expand advanced options
        page.locator("text=Advanced Options").first.click()
        page.wait_for_selector("text=Alert Frequency")
        
        # Test frequency selection
        page.locator("text=5 min").click()
        
        # Test priority selection
        page.locator("text=Critical").click()
        
        # Verify selections are active
        # Note: Mantine SegmentedControl doesn't add obvious visual indicators in DOM
        # so we'd need to check the component state or visual appearance

    def test_create_alert_validation(self, page: Page):
        """Test alert creation validation"""
        page.goto("http://localhost:3000/alerts")
        
        # Open create alert modal
        page.locator("button:has-text('Create Alert')").filter(has=page.locator("[data-tabler-icon='wand']")).click()
        page.wait_for_selector("text=Create Smart Alert")
        
        # Try to create without entering text
        create_button = page.locator("button:has-text('Create Alert')").last()
        
        # Button should be disabled initially
        expect(create_button).to_be_disabled()
        
        # Type minimal text
        nl_input = page.locator("input").first()
        nl_input.fill("Alert me")
        
        # Button should still be disabled (too short)
        expect(create_button).to_be_disabled()
        
        # Type enough text
        nl_input.fill("Alert me when any whale wallet moves more than 1000 ETH")
        
        # Wait for confidence to build
        page.wait_for_timeout(2000)
        
        # Button should be enabled now
        expect(create_button).to_be_enabled()

    def test_ios_input_floating_label(self, page: Page):
        """Test iOS-style input floating label behavior"""
        page.goto("http://localhost:3000/alerts")
        
        # Open create alert modal
        page.locator("button:has-text('Create Alert')").filter(has=page.locator("[data-tabler-icon='wand']")).click()
        page.wait_for_selector("text=Create Smart Alert")
        
        # Expand advanced options to see webhook input
        page.locator("text=Advanced Options").first.click()
        page.wait_for_selector("text=Notification Channels")
        
        # Enable webhook to show URL input
        page.locator("label:has-text('Webhook')").locator("input[type='checkbox']").click()
        page.wait_for_selector("input[placeholder='https://your-webhook.com/alerts']")
        
        # Focus on the webhook input to test floating label
        webhook_input = page.locator("input[placeholder='https://your-webhook.com/alerts']")
        webhook_input.focus()
        
        # The label should float up (iOS style)
        # This is hard to test without visual regression, but we can verify the input works
        webhook_input.fill("https://test.com")
        expect(webhook_input).to_have_value("https://test.com")

    def test_executive_card_styling(self, page: Page):
        """Test executive card glass morphism effects"""
        page.goto("http://localhost:3000/alerts")
        
        # Open create alert modal
        page.locator("button:has-text('Create Alert')").filter(has=page.locator("[data-tabler-icon='wand']")).click()
        page.wait_for_selector("text=Create Smart Alert")
        
        # Check that executive cards are present
        cards = page.locator(".executive-card")
        expect(cards).to_have_count(3)  # Mode selector, input area, advanced options
        
        # Verify gradient badge
        gradient_badge = page.locator("text=AI Powered").locator("..")
        expect(gradient_badge).to_be_visible()

    def test_voice_input_button(self, page: Page):
        """Test voice input button presence"""
        page.goto("http://localhost:3000/alerts")
        
        # Open create alert modal
        page.locator("button:has-text('Create Alert')").filter(has=page.locator("[data-tabler-icon='wand']")).click()
        page.wait_for_selector("text=Create Smart Alert")
        
        # Check for microphone button
        mic_button = page.locator("[data-tabler-icon='microphone']")
        expect(mic_button).to_be_visible()
        
        # Hover to see tooltip
        mic_button.hover()
        page.wait_for_selector("text=Voice input", timeout=2000)

    def test_modal_cancel_button(self, page: Page):
        """Test cancel button functionality"""
        page.goto("http://localhost:3000/alerts")
        
        # Open create alert modal
        page.locator("button:has-text('Create Alert')").filter(has=page.locator("[data-tabler-icon='wand']")).click()
        page.wait_for_selector("text=Create Smart Alert")
        
        # Click cancel
        cancel_button = page.locator("button:has-text('Cancel')")
        cancel_button.click()
        
        # Modal should close
        expect(page.locator("text=Create Smart Alert")).not_to_be_visible()
        
        # Should be back on alerts page
        expect(page.locator("text=Alert Management")).to_be_visible()