# UI Refinement Rules (Mobile-First)

## Scope Lock
- Touch UI only (`templates/*`, static styles/scripts, UI route UX behavior).
- Do not remove or rewrite backend features, models, risk logic, OCR, RAG, scraping, or APIs.
- Keep existing route contracts and payloads stable.

## Product Direction
- Mobile-first layout by default, then scale up for desktop.
- Minimal surface area: fewer buttons, clearer hierarchy, faster first actions.
- One primary action per screen section.
- Show friendly states; avoid raw server errors in user-facing UI.

## UX Guardrails
- Unauthenticated UI routes must redirect to login/welcome, not return raw JSON errors.
- Keep sign in and sign up in one clean entry experience.
- Preserve role behavior:
  - user -> user dashboard
  - oem/admin -> OEM dashboard

## Visual System
- Keep a clean blue/neutral palette aligned with current product theme.
- Use high contrast text and large touch targets (44px+ hit area).
- Keep motion subtle and purposeful (entry/transition only).

## Delivery Method
- Make changes section-by-section.
- Do small commits and verify after each step.
- Run tests after each UI batch before deployment.
