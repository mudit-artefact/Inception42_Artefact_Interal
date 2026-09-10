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

**Point at step 4 first.** *Sign your contract* reads **"Opens once your documents have been
checked"** and has no button. That is HCS-11's rule, not ours — it refuses a signature until
the pack is in and checked. Worth saying out loud before you upload anything.

**Send all five papers** from **`3-onboarding-goes-right/`** — everything in that folder,
including her signed job-offer form. Step 2 reads **"5 of 5 sent"**.

**Watch step 3 flip.** *Documents checked* → Completed, and step 4 **opens by itself**. Two
systems agreeing without anybody pressing anything.

**Then Sign your contract.** The contract is drawn from the record and shown *in the panel* —
her position, salary, start date. Read, tick, sign. **The button is dead until she ticks.**

> **The point.** The contract and the signed offer letter are two different documents, and
> the contract comes last. HCS-11 put it plainly when they separated them: filing them as one
> "put a green tick on the checklist against a file nobody had sent."

### It goes wrong — Daniel Okonkwo `EMP015`

Send everything in **`4-onboarding-photo-rejected/`** — passport, photograph and offer.
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
| Layla's document step, before signing | **5 of 5 sent** |
| Layla's contract, before her documents are in | **no button — "opens once your documents have been checked"** |
| Sultan's rows, first upload | **3 pass, 1 fails** |
| Ring on My Onboarding | counts **6**; Day 1 is a date, not a task |

If a number differs, the data has moved — check the person is who you think from the top
right, and that HCS-11 on `:8001` is up.

---

# Conversations to show

The three journeys above prove the system *does* things. This page proves it **knows**
things — across all eleven policies, off the record as well as the book, and in Arabic.

Every question below was asked on this stack on **10 September 2026** and the answers are
what actually came back. Pick four or five; they are grouped by what each one proves.

**Switch person from the top right before asking** — the answer changes with who is asking.

---

## A · It has read the whole People Code, not just leave

| Be | Ask | What comes back |
|---|---|---|
| **Khalifa** `EMP010` | *"If I am signed off sick for six weeks, does my pay change along the way?"* | **Days 1–15 at 100%, days 16–42 at 50%** — and it adds *"with no sick days used yet"*, because it checked |
| **Hessa** `EMP011` | *"Can I work from home three days a week?"* | **No — 2 is your maximum.** Her role is **Class A**, so 2 remote, 3 in office |
| **Hessa** `EMP011` | *"Is there an internet allowance if I work from home?"* | **AED 200 a month**, if you work more than **6 remote days** that month |
| **Daniel Reed** `EMP004` | *"What are the approval thresholds for expense claims?"* | **Under 1,500** manager · **1,500–7,500** manager + Finance · **above 7,500** manager + Finance + **CFO**. And: you can never approve your own |
| **Daniel Reed** `EMP004` | *"What is the per diem for a business trip inside the UAE?"* | **AED 150 a full day** — counting the day you leave, not the day you return |
| **Khalifa** `EMP010` | *"How many days can I be off sick before I need a doctor's note?"* | **Two.** From the **third consecutive day**, a certificate, uploaded within **48 hours** |
| **Khalifa** `EMP010` | *"What happens if someone does not come to work and does not call in?"* | **Unauthorised absence** — unpaid, and may be referred for disciplinary action |
| **Shamma** `EMP007` | *"I want to raise a formal complaint about how my manager treated me."* | Cites **HC-PC-009 §9.2** — and spots that *because the complaint is about her manager*, she may **skip the informal stage** and go straight to People & Culture |
| **Alia** `EMP001` | *"Can I carry my unused annual leave into next year?"* | **Up to 10 days**, and they must be taken by **30 April** or they are lost |
| **Mohammed** `EMP012` | *"If a public holiday falls in the middle of my annual leave, do I lose that day?"* | **No.** Public holidays are not working days, so they do not come off the balance |

> **The one to show if you show only one.** Be **Mohammed** `EMP012` and ask
> *"What is my grade and what does that band mean?"*
>
> > You are **Grade 5**, in the **Senior Professional** band. You do **not** have business
> > class entitlement — that starts at Grade 6. Your probation is **6 months**. You can
> > approve your **own expenses up to AED 1,500**.
>
> Four different policies, resolved against his actual grade, in one answer.

---

## B · It reads your record, not the policy book

Same question, three people, three different true answers. Ask each in turn:

**"How many annual leave days do I have left?"**

| Be | Answer | Why it differs |
|---|---|---|
| **Mohammed** `EMP012` | **16** — 21 entitled, 5 used | The standard entitlement |
| **Shamma** `EMP007` | **10** — 14 entitled, 4 used | She is **0.6 full-time**; pro-rated |
| **Alia** `EMP001` | **15** — 27 entitled, 12 used | Her 27 **includes carry-over** from last year |
| **Tariq** `EMP008` | **None** — *"your employment has ended and any accrued leave was paid out in your final settlement"* | He has left |

> **The point.** Nothing here is recited. Four answers, four records, one question.

And it works the same way on a live case. Be **Layla** `EMP017` and ask
*"What is the deadline for sending my visa documents?"*

> Your case must be complete by **10 October 2026**. The only item still missing is your
> **signed job-offer form** … tell me and I will open the upload window for you here.

The date is policy. The missing item is HCS-11, read live. The offer to open the window is
the system knowing what she can do next.

---

## C · It says when it does not know

Be **Khalifa** `EMP010`: *"How many days of paternity leave do I get?"*

> Your paternity leave entitlement is **not specified in these extracts**, so I cannot state
> the exact number of days for you … please contact People & Culture at
> **people@hcservices.ae**.

It does not guess a number. It says which policy would hold the answer and where to go.

> **Worth saying out loud:** the failure that matters in HR is not "I don't know" — it is a
> confident wrong number that somebody books their year around.

---

## D · It holds the thread, and it asks back

**Two turns, same conversation.** Be **Alia** `EMP001`:

1. *"How many annual leave days do I have?"* → **15 remaining** of 27, 12 used
2. *"And can I carry what is left into next year?"* → **up to 10 days into 2027**, the rest forfeited

The second question names no leave type, no year, no person. It answers anyway.

**And when a question is genuinely ambiguous it does not pick for you.** Ask
*"How much leave do I have?"* → it gives **annual and sick**, then asks:

> Are you looking to book annual leave, submit a sick leave certificate, or do you have
> questions about a specific leave type?

---

## E · Arabic is not a translation layer

Ask in Arabic and the whole answer is built in Arabic, from the Arabic policies — the
sources come back as **HC-PC-002-AR**, not the English ones run through a translator.

**Be Hessa** `EMP011`: *"كم يوم إجازة مرضية أستحق؟"*

> أنتِ تستحقين في المجمل **90 يوماً** — **15 يوماً** بأجر كامل، **45 يوماً** بنصف الأجر،
> **30 يوماً** بدون أجر.

…then, from her record: **لم تستخدمي أي إجازة مرضية بعد** — she has used none. Policy and
record, both in Arabic, in one answer.

**Be Daniel Reed** `EMP004`: *"ما هو الحد الأقصى لتكلفة الفندق في رحلة عمل؟"*

> **دبي وأبوظبي 750** · باقي الإمارات **500** · الشرق الأوسط **600** · أوروبا والولايات
> المتحدة **900** · باقي الدول **700** — درهماً لليلة، دون الضرائب والرسوم البلدية.

The question named no city, so it returned the whole band table and then offered to work
out which one applies if you name where you are going.

---

## Do not ask these

Tested, and they read worse than the versions above.

| Don't | Do | Why |
|---|---|---|
| *"Who has to approve an expense claim of 12,000 dirhams?"* | *"What are the approval thresholds for expense claims?"* | The first one **refuses** — it will not do the arithmetic on your behalf. The second gives the whole ladder |
| *"What is wrong with my claim?"* | *"What is the status of my schooling claim?"* | The first gets a generic policy answer. The second reads the real fault |

---

## If an answer looks wrong on the day

Check the person in the top right first — most surprises are the previous persona still
selected. Then check HCS-11 on `:8001` is up: policy answers survive without it, but
anything about a document, a case or a deadline will say it **could not check** rather than
inventing a state.
