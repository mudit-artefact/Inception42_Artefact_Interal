# Refine three-panel visual hierarchy

## Goal
Make the left conversation panel, middle chat workspace, and right employee panel visually distinct while keeping the interface clean, accessible, and responsive.

## Approach
Apply a subtle hierarchy where the middle chat area is the clear "main stage" and the sidebars read as supporting context.

## Changes

1. **Middle chat workspace**
   - Use the cleanest/lightest surface (`bg-card` or a dedicated workspace token) for the chat panel so it pops forward.
   - Keep the chat panel flush with the header and sidebars, but visually separated by the adjacent sidebar backgrounds.

2. **Left conversation sidebar**
   - Keep `bg-sidebar` as the recessed surface.
   - Retain the right border and current width (260px on `lg` and up).

3. **Right employee sidebar**
   - Keep `bg-sidebar` and the left border.
   - Retain current width (300px on `xl` and up) and overflow behavior.

4. **Header cohesion**
   - Ensure the top header continues to sit above all three columns without visual breaks.

5. **Mobile behavior**
   - No change to the sheet-based mobile navigation.
   - The same panels collapse into the sheet on smaller viewports.

## Outcome
A more scannable enterprise layout: the eye lands on the chat area first, while history and employee context sit clearly in secondary panels.
