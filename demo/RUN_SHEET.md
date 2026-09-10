# Demo run sheet

Three journeys, each shown twice: once when it goes right, once when it does not. The
conversational behaviour is not a separate act — it sits inside the cases.

**Everything you need is in this folder.** The document sets are copied in, already narrowed to what each step uses — no hunting in a file dialog.

**Before you start.** Backend `:8000`, HCS-11 `:8001`, front end `:8080`. Switch person from
the top right; the page redraws around whoever is selected. Every persona, file and number
below was run against this stack on 10 September 2026.

> `CONVERSATION_SCENARIOS.md` is **stale on names** — it calls EMP001 "Ahmed" and EMP007
> "Omar". The seed has Alia and Shamma. Do not open it on the day.

---

## 1 · Schooling

### It goes right — Elena Costa `EMP009`, her son Luca

**Ask first:** *"What does the education allowance cover?"* → answered from **HC-PC-012**,
with the clause cited. Say: it will not answer what the People Code does not contain.

**Then:** *"I want to upload my school documents"* → the window opens on her claim.
Send everything in **`1-schooling-goes-right/`** — four documents.

**Four green rows.** The verdict is HCS-11's, shown once, not recalculated in the browser.

### It goes wrong — Sultan Al Neyadi `EMP006`, his daughter Shaikha

Send everything in **`2-schooling-wrong-child/`** — four documents.
The invoice in that folder belongs to **Hamdan**, his other child.

**Three rows pass. The invoice fails, and says why:**

> This document is for a different child. Please send Shaikha Al Neyadi's documents.

**Then ask:** *"What is the status of my schooling claim?"* — it names the child, the
status, and the actual fault. Not a summary; the reviewer's own words.

**Fix it live:** send **`2-schooling-wrong-child/corrected/`**. Row turns green,
claim settles. Sending again replaces — nothing is deleted.

> **The point.** The fault is against the *document*, not the claim. A version of this
> shipped twice showing green ticks over papers the other system had rejected.

---

## 2 · Leave

### It goes right — Mohammed Al Marri `EMP012` → Alia Al Suwaidi `EMP001`

*"I want to apply for annual leave from 2026-12-14 to 2026-12-16"* → a **confirmation card**,
not a booking. Nothing is written until he presses Confirm.

Switch to **Alia**, his manager → *"What leave requests do I need to approve?"* → her queue,
with Approve and Reject on the row → Approve.

**Watch three things move together:** the request goes Approved, his balance **16 → 13**,
and his bell gains the decision.

### It goes wrong — Shamma Al Muhairi `EMP007`

**Ask:** *"How many annual leave days do I have?"* → **14, not 21.** She is 0.6 full-time and
the entitlement is pro-rated. That number is read off her record, not recited from policy.

**Then:** *"I want to apply for annual leave from 2026-09-21 to 2026-10-02"* — ten days,
starting in three. Refused on **two independent rules at once**:

> Notice period requirement not met: **HC-PC-001 §1.4** requires at least 20 working days
> advance notice for 10 days of annual leave. Only 6 working days notice was provided.
>
> Probation restriction: Your probation status is 'Active'. Under **HC-PC-003 §3.2**,
> annual leave cannot be taken during active probation.

**And it names her manager** — Daniel Reed — as the way forward.

> **The point.** Both rules are checked in code, not by the model. Same question, same
> answer, every time.

---

## 3 · Onboarding

### It goes right — Layla Haddad `EMP017`, resident hire

Open **My Onboarding** — a page only new joiners see. Seven milestones in three columns:
what she does, what HC Services do, her first day. The ring counts what can finish.

**Send four papers** from **`3-onboarding-goes-right/`** — all four in
that folder. The offer is deliberately not there: she signs it on screen.
Step 2 reads **"4 of 4 sent"**.

**Then Sign your contract.** The contract is drawn from the record and shown *in the panel* —
her position, salary, start date. Read, tick, sign. **The button is dead until she ticks.**

**Signing files her signed job-offer form**, so it completes the checklist she was sending —
which is why documents come first and the contract second. Steps 4 and 5 follow: checked,
then with the PRO.

### It goes wrong — Daniel Okonkwo `EMP015`

Send his passport and photograph from **`4-onboarding-photo-rejected/`**.
**The photograph row comes back** with the reason — the background is blue, and the route
requires white. Send **`4-onboarding-photo-rejected/corrected/`** and it turns green.

**Close in Arabic:** *"ما حالة معاملتي؟"* → answered in Arabic, with his real state.

---

## If you have another minute

**Stop HCS-11 and ask Layla about her documents.** It says it *could not check* — it does
not say she has no case. Not knowing and knowing-there-is-nothing are different answers, and
telling somebody who has sent four documents that they have none is the one failure that
matters. Restart it and the same question answers properly.

---

## Numbers to expect

| | Expect |
|---|---|
| Mohammed's balance, after approval | **16 → 13** |
| Shamma's entitlement | **14**, not 21 |
| Layla's document step, before signing | **4 of 4 sent** |
| Sultan's rows, first upload | **3 pass, 1 fails** |
| Ring on My Onboarding | counts **6**; Day 1 is a date, not a task |

If a number differs, the data has moved — check the person is who you think from the top
right, and that HCS-11 on `:8001` is up.
