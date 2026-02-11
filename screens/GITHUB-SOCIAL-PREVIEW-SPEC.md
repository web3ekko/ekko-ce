# GitHub Social Preview Spec: Ekko CE

## Objective
Create a GitHub social preview image that matches the README positioning:
- Avalanche-first
- Natural-language alert creation
- Fast, multi-channel notifications
- Easy self-hosted onboarding
- CTA to full hosted version at `app.ekko.zone`

## Canvas
- Size: `1280 x 640` px (2:1)
- Format: PNG, sRGB
- Safe margin: `80px` on all sides
- Keep all critical text inside safe margin

## Message Hierarchy
1. Headline (primary)
2. Subheadline (proof/value)
3. Trust strip (open-source + runtime stack)
4. CTA line (hosted version)

## Recommended Copy (V1)
- Headline: `Natural-Language Alerts for Avalanche Teams`
- Subheadline: `Open-source monitoring with fast, multi-channel notifications.`
- Trust strip: `Django + React + NATS + wasmCloud`
- CTA line: `Run CE locally. Use app.ekko.zone for the full managed version.`

## Alternate Copy (Short)
- Headline: `Avalanche Monitoring, in Plain English`
- Subheadline: `Build alerts fast. Notify instantly. Self-host in minutes.`
- CTA line: `Ekko CE + app.ekko.zone`

## Layout
Use a split composition:
- Left column (`~58% width`): text block
- Right column (`~42% width`): product visual stack (dashboard + alert detail crops)

### Left Column Placement
- Top: Ekko mark + `Ekko CE`
- Middle: headline (2 lines max), subheadline
- Bottom: trust strip chips + CTA line

### Right Column Placement
- Main card: dashboard screenshot crop (`screens/02-dashboard-logged-in.png`)
- Overlay card: alert detail/notification crop (`screens/14-alert-detail-notifications-open.png`)
- Small badge accent: `Avalanche-first` chip

## Visual Direction
- Style: clean SaaS, light-surface, high-contrast
- Background: soft gradient (no dark background)
- Depth: subtle shadows, 1px borders, rounded cards
- Avoid: noisy textures, heavy glows, crowded text

## Color Tokens
- Background base: `#F7F9FC`
- Background gradient accent: `#EAF1FF`
- Primary text: `#0F172A`
- Secondary text: `#334155`
- Primary brand/action: `#2563EB`
- Avalanche accent: `#E84142`
- Success accent (speed/live): `#10B981`
- Card border: `#E6E9EE`

## Typography
- Family: `Inter` (or closest modern sans if unavailable)
- Headline: `64-72px`, weight `700-800`, line-height `1.05-1.1`
- Subheadline: `30-34px`, weight `500-600`, line-height `1.2`
- Trust strip / CTA: `22-26px`, weight `500-600`

## Trust Strip Chips (Recommended)
Use 3 small pills:
- `Open Source`
- `NATS + wasmCloud`
- `Multi-Channel Alerts`

## Accessibility Rules
- Minimum text contrast: WCAG AA against background
- No text over busy image areas
- Keep headline to max 2 lines
- Do not place important copy near edges

## Export Checklist
- [ ] Correct size: 1280x640
- [ ] PNG, sRGB
- [ ] Readable at small preview sizes
- [ ] Headline visible in first glance
- [ ] `app.ekko.zone` legible
- [ ] Product screenshot visible but secondary to message

## Suggested File Names
- `social-preview-ekko-ce-v1.png`
- `social-preview-ekko-ce-v2.png`
- `social-preview-ekko-ce-final.png`

## GitHub Upload
Repository -> Settings -> General -> Social preview -> Upload `social-preview-ekko-ce-final.png`

## Ready-to-Use AI Design Prompt
Design a GitHub social preview image for an open-source SaaS product called Ekko CE. Canvas 1280x640. Clean light SaaS style with soft gradient background (#F7F9FC to #EAF1FF), high-contrast dark text (#0F172A), blue brand accent (#2563EB), Avalanche red accent (#E84142). Left side text: "Natural-Language Alerts for Avalanche Teams" and "Open-source monitoring with fast, multi-channel notifications." Add trust chips: "Open Source", "NATS + wasmCloud", "Multi-Channel Alerts". Add CTA line: "Run CE locally. Use app.ekko.zone for the full managed version." Right side: layered UI cards using a dashboard and notification panel feel. Rounded cards, subtle border #E6E9EE, soft shadows, modern premium SaaS look.
