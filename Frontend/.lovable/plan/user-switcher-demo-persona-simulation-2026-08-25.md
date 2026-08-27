# User Switcher (Demo Persona Simulation)

Add a way to switch the signed-in employee so you can demo how the concierge looks for different people, without any backend work.

## What you get

- A user chip in the top-right of the header showing avatar initials, name and job title.
- Clicking it opens a dropdown listing 3-4 mock employees; the current one is check-marked.
- Picking a different employee instantly updates:
  - The right-hand employee card (name, title, department, grade, manager, leave balances).
  - The policy links shown for that employee (each persona gets a relevant set).
  - The conversation history, which is stored per employee, so each persona has their own threads and the chat resets to a fresh conversation on switch.
- The selected employee persists across reloads.
- On mobile the same switcher appears at the top of the slide-out panel.

## Mock personas

Four contrasting profiles so differences are visible:
1. Mohammad Mohsen — Senior Systems Analyst, Grade 9 (current profile).
2. A newly joined employee on probation with low accrued balances.
3. A department head / manager with higher entitlement and extra manager-oriented policy links.
4. A part-time / clinical staff member with different leave units.

Mock chat answers that mention balances will use the active employee's numbers so replies stay consistent with the card.

## Technical notes

- Extend `src/lib/api/mock.ts` with a `MOCK_EMPLOYEES` array (each with its own `policyLinks`), keeping `MOCK_EMPLOYEE` as the default export for compatibility.
- New `src/hooks/useActiveEmployee.ts` (or a small context in `src/lib/employee-context.tsx`) holding the active employee id in `localStorage`.
- New `src/components/concierge/UserSwitcher.tsx` using existing shadcn `DropdownMenu` + `Avatar`; navy primary avatar with pink ring on the active item, consistent with current tokens.
- `src/hooks/useConcierge.ts`: namespace the `localStorage` history key by employee id and reset `activeId` when the employee changes.
- `src/routes/index.tsx`: render `UserSwitcher` in the header and inside the mobile sheet; pass the active employee and its policy links to `EmployeeCard`.
- Balance-related mock answers accept the active employee so numbers match; no API contract changes (`POST /chat` payload stays `{ message, conversation_id }`).
