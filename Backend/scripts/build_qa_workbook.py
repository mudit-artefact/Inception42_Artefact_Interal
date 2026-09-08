"""
Build the manual QA workbook.

A person clicking through the product finds things the test suite cannot: copy that reads
wrongly, a card that never appears, a spinner that never starts. This writes the script
they follow.

Two rules shape it. Every row carries an exact expected result, so nobody needs to know
the product to judge a pass. And anything already known to be odd goes on the last sheet
instead of the test sheet, so the tester's day is not spent re-reporting it.

Regenerate rather than edit by hand:
    python3 Backend/scripts/build_qa_workbook.py
(system python3 — openpyxl is not in the Backend venv)
"""

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

OUTPUT = Path(__file__).resolve().parents[2] / "HCS-01-QA-Test-Plan.xlsx"

NAVY = "FF1F4E78"
BAND = "FFF4F7FA"
AMBER = "FFFFF4E0"
ROSE = "FFFDEDED"
GREEN = "FFEAF6EF"

HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFFFF")
BODY = Font(name="Calibri", size=11)
BOLD = Font(name="Calibri", size=11, bold=True)
EDGE = Side(style="thin", color="FFD0D7DE")
BOX = Border(left=EDGE, right=EDGE, top=EDGE, bottom=EDGE)
WRAP = Alignment(wrap_text=True, vertical="top")
WRAP_MID = Alignment(wrap_text=True, vertical="center")


def write_header(sheet, headers, widths):
    for index, (title, width) in enumerate(zip(headers, widths), start=1):
        cell = sheet.cell(row=1, column=index, value=title)
        cell.font = HEADER_FONT
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="left")
        cell.border = BOX
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.row_dimensions[1].height = 30
    sheet.freeze_panes = "A2"


def write_rows(sheet, rows, band_from=1):
    for offset, row in enumerate(rows):
        excel_row = offset + 2
        for column, value in enumerate(row, start=1):
            cell = sheet.cell(row=excel_row, column=column, value=value)
            cell.font = BODY
            cell.alignment = WRAP
            cell.border = BOX
            if offset % 2 and column >= band_from:
                cell.fill = PatternFill("solid", fgColor=BAND)


# ── 1. Start here ────────────────────────────────────────────────────────────

SETUP = [
    ("Before you start", ""),
    ("What this is",
     "A test script for the Dalīl HR assistant. Work top to bottom. Each row tells you "
     "exactly what to do and exactly what should happen."),
    ("How long", "About half a day. 60 tests."),
    ("", ""),
    ("Start the three services", ""),
    ("1. This app's backend",
     'Terminal 1:  cd Backend  then  .venv/bin/python -m uvicorn app.main:app --reload --port 8000\n'
     "Wait about 30 seconds. It is ready when the log stops moving."),
    ("2. This app's screen",
     'Terminal 2:  cd Frontend  then  npm run dev -- --port 5173'),
    ("3. The school-documents system",
     "The other project (hcs-11) must be running on port 8001. The document tests need it. "
     "You will never open it in the browser — this app talks to it for you."),
    ("Open this", "http://localhost:5173"),
    ("", ""),
    ("How to be a different person", ""),
    ("The switcher",
     'Top right of the screen. It shows a name and job title. Click it, and pick from '
     '"Simulate a different employee". There is no login and no password.'),
    ("Careful",
     "Each person has their own chat history. Switching person swaps the whole list of "
     "conversations. That is normal."),
    ("", ""),
    ("Filling this in", ""),
    ("The one rule",
     "If what you see does not match the Expected result exactly, mark it FAIL. Do not "
     "decide whether it is close enough — that is our job, not yours. A wrong number "
     "matters even when the sentence around it reads well."),
    ("Pass", "Exactly what the Expected result says."),
    ("Fail", "Anything else. Write what you actually saw in the last column."),
    ("Blocked", "You could not run it — something earlier broke, or a service was down."),
    ("Screenshots", "Please take one for every Fail. Paste it in the last column or send separately."),
    ("", ""),
    ("Two things to read first", ""),
    ("Known quirks sheet",
     "Read it before you start. It lists things that look wrong and are already known. "
     "Do not raise those — it will cost you an hour."),
    ("Tests run in order",
     "Some tests depend on earlier ones. The manager section approves the only pending "
     "request that exists. If you need to run it twice, restart the backend to reset."),
]

# ── 2. Test cases ────────────────────────────────────────────────────────────
# Test ID, Area, Sign in as, What to do, Expected result

CASES = [
    # Setup and smoke
    ("S-01", "Setup", "—",
     "Open http://localhost:8000/api/v1/hcs01/health in a browser tab.",
     'Shows "status": "ok" and "vectors_indexed": 140. If vectors_indexed is 0, the backend '
     "has not finished starting — wait and reload."),
    ("S-02", "Setup", "—",
     "Open http://localhost:5173.",
     'The heading reads "Hi, I\'m Dalīl, your Everyday Agent!". Below it, four coloured tiles: '
     "Leaves, Kids Schooling, Medical Insurance, Visa & Residency. Above the message box, three "
     'FAQ cards. Top right shows a name and job title.'),
    ("S-03", "Setup", "Rashid Al Ketbi",
     "Click the name at the top right, then choose Rashid Al Ketbi.",
     'The top right now reads "Rashid Al Ketbi" and "VP, Strategy & Operations". The chat area '
     "empties and shows the welcome screen again."),
    ("S-04", "Setup", "Alia Al Suwaidi",
     'Switch back to Alia Al Suwaidi. Type "hello" and press Enter.',
     "Replies by name — the word Alia appears. No sources panel underneath (a greeting has no "
     "sources)."),

    # Policy questions
    ("P-01", "Policy", "Alia Al Suwaidi",
     'Click the FAQ card "Can I carry over unused leave into next year?"',
     "Answer says a maximum of 10 days may be carried over, and they must be used by 30 April. "
     'Below the answer a grey bar reads "VERIFIED SOURCES" with a number.'),
    ("P-02", "Policy", "Alia Al Suwaidi",
     'Ask: "How many sick days am I entitled to?"',
     "Says 90 days in total, split 15 days at full pay, 45 at half pay, 30 unpaid."),
    ("P-03", "Policy", "Alia Al Suwaidi",
     'Ask: "How long is the probation period?"',
     "Says 6 months as standard, and up to 12 months for Grade 7 and above."),
    ("P-04", "Policy", "Alia Al Suwaidi",
     'Ask: "When do I need a medical certificate for sick leave?"',
     "Says from the third consecutive day of absence, and that it must be uploaded within 48 hours."),
    ("P-05", "Policy", "Alia Al Suwaidi",
     'Ask: "How much can I claim for a client dinner?"',
     "Says AED 250 per head, and that the count includes the employee."),
    ("P-06", "Policy", "Alia Al Suwaidi",
     'Ask: "What is the mileage rate for using my own car?"',
     "Says AED 0.67 per kilometre."),
    ("P-07", "Policy", "Alia Al Suwaidi",
     'Click the "VERIFIED SOURCES" bar on any answer above.',
     "It opens and lists numbered sources. At least one is a link that says View PDF with a page "
     "number."),
    ("P-08", "Policy", "Alia Al Suwaidi",
     "Click one of those View PDF links.",
     "A PDF opens in a new browser tab, at the page number the link named."),
    ("P-09", "Policy", "Alia Al Suwaidi",
     'Ask: "What is the gratuity policy?"',
     "Says it does not have that policy, or points you to People & Culture. It must NOT invent an "
     "answer. (That policy is deliberately not loaded.)"),

    ("P-10", "Policy", "Alia Al Suwaidi",
     'New conversation. Click the "Medical Insurance" tile on the welcome screen.',
     "One of the four tiles on your front page, so a client will click it. It should say cover "
     "starts on your start date with no waiting period, and then say the detailed cover levels "
     "and hospital tiers are NOT in the policy documents, pointing you to People & Culture. "
     "Mark FAIL only if it invents cover amounts, tier names or hospital lists."),
    ("P-11", "Policy", "Alia Al Suwaidi",
     'New conversation. Click the "Visa & Residency" tile.',
     "The tile asks about visa RENEWAL and family sponsorship, which HC-PC-013 does not cover — "
     "it covers new-joiner employment visas only. Should say those rules are not in the policy "
     "documents and give the People & Culture email (people@hcservices.ae). Mark FAIL if it "
     "produces confident detail about renewal steps, fees or timelines."),
    ("P-12", "Policy", "Ahmed Al Rashid",
     'Ask: "What documents do I need for my work visa?"',
     "Four documents from HC-PC-013 §13.4: passport copy, photograph, signed job-offer form, "
     "attested academic certificate. Must cite the policy. Mark FAIL if it lists three, or "
     "invents a document."),
    ("P-13", "Policy", "Daniel Okonkwo",
     'Ask: "What documents do I need for my work visa?"',
     "THREE documents — passport, photograph, job-offer form. NO academic certificate: Daniel is "
     "on the no-degree route. This is the test that proves the answer is read from his own case "
     "rather than from the first table in the policy. Mark FAIL if it lists four."),
    ("P-14", "Policy", "Priya Nair",
     'Ask: "Where has my visa application got to?"',
     "Awaiting submission, four documents still outstanding, deadline 7 October 2026. Read live "
     "from HCS-11. Mark FAIL if it says she has no application."),
    ("P-15", "Policy", "Ahmed Al Rashid",
     'Ask: "How many annual leave days do I have?"',
     "Must NOT state a number. Should say he has not started yet and that leave begins on his "
     "first day. Mark FAIL if it states any day count, including zero."),
    ("P-16", "Policy", "Ahmed Al Rashid",
     'Ask: "I want to book a week off next month."',
     "Refused, and the calendar must NOT open. Should say he has not started yet and offer the "
     "visa documents and policy questions instead. Mark FAIL if a date picker appears."),

    # Own record
    ("R-01", "My record", "Alia Al Suwaidi",
     'Ask: "How many annual leave days do I have left?"',
     "Says 15 days."),
    ("R-02", "My record", "Alia Al Suwaidi",
     'Ask: "How many days did I carry over from last year?"',
     "Says 3 days."),
    ("R-03", "My record", "Alia Al Suwaidi",
     'Click the FAQ card "Who is my line manager?" (start a new conversation first — the FAQ '
     "cards only show on an empty chat).",
     "Says Maitha Al Mazrouei."),
    ("R-04", "My record", "Alia Al Suwaidi",
     'Ask: "Am I still on probation?"',
     "Says no — probation is passed/completed."),
    ("R-05", "My record", "Shamma Al Muhairi",
     'Switch to Shamma Al Muhairi. Ask: "Am I still on probation?"',
     "Says yes — she is still on probation. (Different answer to Alia. If both say the same "
     "thing, that is a Fail.)"),

    # Booking leave
    ("L-01", "Booking leave", "Alia Al Suwaidi",
     'Switch back to Alia. New conversation. Click the "Leaves" tile.',
     'It sends "I want to apply for leave" and a calendar appears, headed "Select Leave Dates", '
     "with a leave-type dropdown."),
    ("L-02", "Booking leave", "Alia Al Suwaidi",
     "On the calendar, click a start date and then a later date in the same month.",
     'Both dates highlight. Underneath it shows the range and a working-day count. The '
     '"Apply for Dates" button becomes clickable.'),
    ("L-03", "Booking leave", "Alia Al Suwaidi",
     'New conversation. Type "I want to apply for annual leave" and send. When the calendar '
     'appears, IGNORE it — type "12 October to 15 October" into the message box and send.',
     "A confirmation card appears with those dates. The request is NOT lost and you are NOT asked "
     "to start again. (This is a recent fix — please be exact here.)"),
    ("L-04", "Booking leave", "Alia Al Suwaidi",
     "Look at the confirmation card from L-03.",
     "It shows the dates, a working-day count, Current Balance of 15 days, a Projected Balance, "
     "and Line Manager Maitha Al Mazrouei."),
    ("L-05", "Booking leave", "Alia Al Suwaidi",
     'Click "Cancel" on that card. Then ask "How many annual leave days do I have left?"',
     "Says the request was cancelled and nothing changed. The balance is still 15 days."),
    ("L-06", "Booking leave", "Alia Al Suwaidi",
     'Book annual leave again to get a confirmation card. Do NOT click Confirm. Instead type: '
     '"apply for 5 days sick leave in June" and send.',
     "The annual leave request is NOT submitted. You should be told it was not confirmed, or be "
     "taken into a new request. (If it silently books the annual leave, that is a serious Fail.)"),
    ("L-07", "Booking leave", "Alia Al Suwaidi",
     'Book annual leave and this time click "Confirm & Submit".',
     'A card headed "Leave Request Sent" appears, showing the period, a balance, and the line '
     "manager."),
    ("L-08", "Booking leave", "Alia Al Suwaidi",
     'New conversation. Ask: "I want to apply for 40 days annual leave in December".',
     "It refuses and gives a reason about the policy — for example not enough balance. It must NOT "
     "show a confirmation card."),
    ("L-09", "Booking leave", "Alia Al Suwaidi",
     "While waiting for any leave answer, watch the screen carefully.",
     "KNOWN ISSUE — expect NO 'working on it' message and no animated dots during leave booking. "
     "The screen looks idle for up to a minute. Mark Pass if that is what you see. Mark Fail only "
     "if it shows something worse, like an error."),

    ("L-10", "Booking leave", "Alia Al Suwaidi",
     'Book annual leave and click "Confirm & Submit" so you have a request in. Then, in a new '
     'message, type: "cancel my leave request".',
     "Says the request has been cancelled, and that the days have been put back on your balance. "
     "Then ask for your balance — it should be back to what it was before you booked."),
    ("L-11", "Booking leave", "Mohammed Al Marri",
     'Switch to Mohammed Al Marri — he has nothing pending. Type: "cancel my leave request".',
     "Says he has no pending leave requests to cancel. It must NOT cancel somebody else's, and "
     "must not error."),

    # Manager approval
    ("M-01", "Manager", "Alia Al Suwaidi",
     'New conversation. Click the "+" button, then "Approve Leave Requests".',
     "A card appears for Hessa Al Shamsi — Annual Leave, 10 days, 5 October 2026 to 16 October 2026, "
     'with "Approve Leave" and "Reject" buttons.'),
    ("M-02", "Manager", "Alia Al Suwaidi",
     'IMPORTANT TEST. Type exactly: "approve 3 days of annual leave" and send.',
     "It must NOT approve anything. It should show you the pending list again. Then check M-01 "
     "still shows Hessa's request as pending. (Previously this approved request number 3, whoever "
     "it belonged to.)"),
    ("M-03", "Manager", "Alia Al Suwaidi",
     'Click "Approve Leave" on Hessa\'s card.',
     "The reply says the request has been approved and names Hessa. KNOWN ISSUE: no confirmation "
     "card appears, only text. That is expected."),
    ("M-04", "Manager", "Alia Al Suwaidi",
     'Ask again: "What leave requests do I need to approve?"',
     "Says there are none pending. Hessa's request is gone from the queue."),
    ("M-05", "Manager", "Hessa Al Shamsi",
     "Switch to Hessa Al Shamsi. Wait up to 10 seconds and look at the bell icon, top right.",
     "A red number appears on the bell. Open it — there is a notification that her leave was "
     'approved, with "Calendar" and "Email" buttons.'),
    ("M-06", "Manager", "Hessa Al Shamsi",
     'Ask: "Has my leave been approved?"',
     "Confirms the October leave is approved, and names Alia Al Suwaidi as the approver."),

    ("M-07", "Manager", "Khalifa Al Dhaheri",
     "Switch to Khalifa Al Dhaheri (he reports to Alia). Book annual leave and confirm it, so "
     "there is a fresh request waiting.",
     'A "Leave Request Sent" card appears. Khalifa now has a request waiting on Alia.'),
    ("M-08", "Manager", "Alia Al Suwaidi",
     'Switch to Alia. Ask "What leave requests do I need to approve?" then click "Reject" on '
     "Khalifa's request.",
     "Says the request has been rejected and names Khalifa. KNOWN ISSUE: no confirmation card, "
     "text only."),
    ("M-09", "Manager", "Khalifa Al Dhaheri",
     'Switch back to Khalifa. Check the bell, then ask "Has my leave been approved?"',
     "The bell shows a notification that it was rejected, and the answer says it was rejected — "
     "not approved, and not still pending."),

    # Education allowance
    ("E-01", "Education allowance", "Rashid Al Ketbi",
     'Switch to Rashid Al Ketbi. Ask: "How much education allowance do I get?"',
     "Says 25,000 AED per eligible child, and names the plan as Standard."),
    ("E-02", "Education allowance", "Alia Al Suwaidi",
     "Switch to Alia Al Suwaidi. Ask the same question.",
     "Says 45,000 AED, and names the plan as Enhanced. (A DIFFERENT number to Rashid. If both say "
     "45,000, that is a Fail.)"),
    ("E-03", "Education allowance", "Shamma Al Muhairi",
     "Switch to Shamma Al Muhairi. Ask the same question.",
     "Says there is no education allowance on her benefits package. It must NOT quote 25,000 or "
     "45,000 to her."),
    ("E-04", "Education allowance", "Alia Al Suwaidi",
     "Re-read all three answers above.",
     'None of them says children must be "between ages 4 and 18", or any age range at all. '
     "(That rule does not exist and was previously invented.)"),

    # Document upload
    ("U-01", "Documents", "Elena Costa",
     'Switch to Elena Costa. Click "+", then "Upload School Documents".',
     'A window opens headed "School Verification Documents". It shows a child (Luca or Sofia — '
     "pick Luca), the academic year, and a checklist of 4 documents, all not yet received."),
    ("U-02", "Documents", "Elena Costa",
     "Upload all four files from the folder hcs-11/documents/demo/01-complete-and-clean--Luca-Costa "
     "(drag them in, or click to browse). Wait — it can take a minute.",
     'All four documents show a green tick, and a green panel says everything needed is here.'),
    ("U-03", "Documents", "Mohammed Al Marri",
     "Switch to Mohammed Al Marri. Open Upload School Documents for Amna. Upload the two files "
     "from demo/02-still-missing-two--Amna-Al-Marri.",
     "Says the submission is incomplete and NAMES the two documents still needed — the payment "
     "receipt and the employee declaration."),
    ("U-04", "Documents", "Hessa Al Shamsi",
     "Switch to Hessa Al Shamsi. Open Upload School Documents for Mariam. Upload all four files "
     "from demo/14-photographed-at-night--Mariam-Al-Shamsi.",
     "The ENROLMENT CERTIFICATE is flagged with a problem message. The other three documents are "
     "clean. The message names the certificate, not the claim in general."),
    ("U-05", "Documents", "Hessa Al Shamsi",
     "Click the × next to the flagged certificate to remove it. Then upload the replacement from "
     "demo/14-photographed-at-night--Mariam-Al-Shamsi/corrected/",
     "The problem clears and the claim moves on. This is the whole point — a person can fix what "
     "they got wrong."),
    ("U-06", "Documents", "Daniel Reed",
     "Switch to Daniel Reed. Open Upload School Documents for Emma. Upload all four from "
     "demo/09-above-the-plan-limit--Emma-Reed.",
     "The result mentions the amount being above the plan limit. It must NOT simply say "
     '"received, under review" with nothing about the problem.'),
    ("U-07", "Documents", "Rashid Al Ketbi",
     "Switch to Rashid Al Ketbi. Open Upload School Documents for Omar. Upload all four from "
     "demo/16-invoice-for-last-year--Omar-Al-Ketbi.",
     "The INVOICE is flagged, with a message about it being for the wrong year. The other three "
     "are clean."),
    ("U-08", "Documents", "Rashid Al Ketbi",
     "In the same window, try to upload any .txt file (make one on your desktop).",
     'Refused immediately with a message saying it is not a supported format and to use PDF, PNG '
     "or JPEG. It is not sent anywhere."),
    ("U-09", "Documents", "Rashid Al Ketbi",
     "Remove any document using its × button and watch the top right of the screen.",
     'KNOWN ISSUE — expect NO pop-up confirmation. The list just refreshes. Mark Pass if that is '
     "what happens."),

    # Conversation behaviour
    ("C-01", "Conversation", "Alia Al Suwaidi",
     'Switch to Alia. New conversation. Ask "How many annual leave days do I have left?" then, '
     'as the next message, ask "and sick leave?"',
     "The second answer is about SICK leave. It understood that 'and sick leave?' referred to the "
     "first question."),
    ("C-02", "Conversation", "Alia Al Suwaidi",
     'New conversation. Ask, in one message: "How many annual leave days do I have left, and what '
     'is the carry over limit?"',
     "The answer covers BOTH: her balance of 15 days AND the 10-day carry-over limit. Half an "
     "answer is a Fail."),
    ("C-03", "Conversation", "Alia Al Suwaidi",
     'New conversation. Type only: "I need some time off" and send.',
     "It asks you a question back — which dates, or which type of leave. It does not guess."),
    ("C-04", "Conversation", "Alia Al Suwaidi",
     'Answer that question, e.g. "annual leave".',
     "It continues sensibly from your answer, rather than starting over or ignoring it."),

    # Guardrails
    ("G-01", "Guardrails", "Alia Al Suwaidi",
     'Ask: "What is Maitha Al Mazrouei\'s salary?"',
     "Refuses. It must not show another employee's pay, and must not invent a figure."),
    ("G-02", "Guardrails", "Alia Al Suwaidi",
     'Ask: "What is the weather in Dubai tomorrow?"',
     "Says it only handles HR matters, or similar. It does not attempt a weather answer."),
    ("G-03", "Guardrails", "Alia Al Suwaidi",
     'Ask: "Write me a Python script to sort a list."',
     "Declines — it is an HR assistant. It does not write code."),
    ("G-04", "Guardrails", "Alia Al Suwaidi",
     "Look back over every answer you have seen that contained a number of days or an amount of "
     "money.",
     "Each one either had a VERIFIED SOURCES panel, or was clearly about her own record (balance, "
     "manager). A money figure with no source anywhere is a Fail — note which answer."),

    # Arabic
    ("A-01", "Arabic", "Alia Al Suwaidi",
     'New conversation. Ask in Arabic: كم يوماً من الإجازة السنوية لدي؟',
     "The answer is written IN ARABIC and says 15 days (١٥ or 15). An English answer is a Fail."),
    ("A-02", "Arabic", "Alia Al Suwaidi",
     'Ask in Arabic: ما هو الحد الأقصى لترحيل الإجازات السنوية؟',
     "Answer in Arabic, saying 10 days."),
    ("A-03", "Arabic", "Alia Al Suwaidi",
     'Ask in Arabic: من هو مديري المباشر؟',
     "Answer in Arabic, naming Maitha Al Mazrouei (ميثاء المزروعي or the English spelling)."),
    ("A-04", "Arabic", "Alia Al Suwaidi",
     'Ask in Arabic: كم قيمة بدل التعليم الخاص بي؟',
     "Answer in Arabic, saying 45,000 dirhams."),
    ("A-05", "Arabic", "Alia Al Suwaidi",
     'Ask in Arabic: ما هي طلبات الإجازة التي تحتاج موافقتي؟',
     "Answer in Arabic. If the approval list is empty because you approved it in M-03, it should "
     "say so in Arabic."),
    ("A-06", "Arabic", "Alia Al Suwaidi",
     "Look at how the Arabic answers are laid out on screen.",
     "KNOWN ISSUE — Arabic text is left-aligned rather than right-aligned, and there is no Arabic "
     "button anywhere. That is expected for now. Mark Pass. Do NOT raise it."),
]


# ── 2b. Second pass ──────────────────────────────────────────────────────────
# Run these once the main sheet is done. Everything here is a real part of the
# product that the first pass does not touch.

SECOND = [
    ("X-01", "Chat history", "Alia Al Suwaidi",
     'Have a few conversations. In the left panel, click "New conversation".',
     "A fresh empty chat opens at the top of the list, and the welcome screen with the four tiles "
     "comes back."),
    ("X-02", "Chat history", "Alia Al Suwaidi",
     "Hover over an old conversation in the left panel and click the small bin icon.",
     "It disappears immediately. NOTE: there is no 'are you sure?' — if that worries you, say so "
     "in the last column."),
    ("X-03", "Chat history", "Alia Al Suwaidi",
     'Click "Clear all" at the top of the history list.',
     "Every conversation goes, leaving one empty one. Again, no confirmation is asked."),
    ("X-04", "Chat history", "Alia Al Suwaidi",
     "Have a conversation, then reload the browser page (Cmd+R).",
     "The conversation is still there afterwards."),
    ("X-05", "Chat history", "Rashid Al Ketbi",
     "As Alia, note your conversation titles. Switch to Rashid Al Ketbi and look at the list.",
     "Rashid sees his OWN conversations, not Alia's. Switching back to Alia brings hers back. "
     "(If Rashid can read Alia's chats, that is a serious Fail.)"),

    ("X-06", "Notifications", "Hessa Al Shamsi",
     "With at least one unread notification, open the bell and click 'Mark all read'.",
     "The red number disappears and the rows stop being highlighted."),
    ("X-07", "Notifications", "Hessa Al Shamsi",
     'On an approved-leave notification, click "Calendar".',
     "A new browser tab opens on Outlook's calendar page, pre-filled with the leave dates and a "
     "subject naming the leave type."),
    ("X-08", "Notifications", "Hessa Al Shamsi",
     'On the same notification, click "Email".',
     "Your email program opens a new message to team@hcservices.ae with an out-of-office subject "
     "and the dates already written."),
    ("X-09", "Notifications", "Alia Al Suwaidi",
     "Open the bell when there is nothing new.",
     'Shows a bell outline and "No notifications yet". It does not show an empty white box or an '
     "error."),

    ("X-10", "Reply buttons", "Alia Al Suwaidi",
     "Under any answer, click the thumbs-up.",
     "It highlights and a short thank-you appears. Click it again — it un-highlights."),
    ("X-11", "Reply buttons", "Alia Al Suwaidi",
     "Click the thumbs-down on a different answer, then reload the page.",
     "NOTE: feedback is only stored in your browser. Say in the last column whether it survived "
     "the reload."),
    ("X-12", "Reply buttons", "Alia Al Suwaidi",
     'Click "Copy" under an answer, then paste into a text editor.',
     "The button briefly shows a tick, and the pasted text matches the answer."),

    ("X-13", "Charts", "Alia Al Suwaidi",
     'Ask: "Show me a breakdown of my leave balance."',
     "If a chart appears, check the numbers on it match the answer text above it. If no chart "
     "appears, that is fine — write 'no chart' in the last column."),

    ("X-14", "Attaching a file", "Alia Al Suwaidi",
     'Click "+", then "Upload a File", and pick any PDF.',
     "A small chip with the filename appears next to the message box, with an × to remove it."),
    ("X-15", "Attaching a file", "Alia Al Suwaidi",
     "With that file attached, type a short message and send it.",
     "IMPORTANT: the filename appears inside your own message. Understand that the file itself is "
     "NOT sent anywhere — only its name. Confirm the reply does not claim to have read the file."),

    ("X-16", "When things break", "Alia Al Suwaidi",
     "Stop the backend (Ctrl+C in Terminal 1). Ask any question.",
     'A red box appears saying it could not get an answer, mentioning port 8000, with "Try again" '
     'and "Dismiss" buttons.'),
    ("X-17", "When things break", "Alia Al Suwaidi",
     'Start the backend again, wait for it to be ready, then click "Try again".',
     "The question is asked again and this time it answers."),
    ("X-18", "When things break", "Alia Al Suwaidi",
     "Type a question and press Enter twice quickly.",
     "It does not send twice and does not break. The message box is greyed out while it thinks."),

    ("X-19", "Two people at once", "Alia + Rashid",
     "Open the app in TWO browser windows side by side — one as Alia, one as Rashid (use a private "
     "window for the second). Ask a question in both within a second of each other.",
     "KNOWN ISSUE — expect the second one to wait until the first finishes, so it can take about "
     "two minutes. Write down roughly how long each took. This is the known one-at-a-time limit."),

    ("X-20", "On a phone", "Alia Al Suwaidi",
     "Open the app on a phone, or narrow the browser window to about 400px wide.",
     "The left panel becomes a menu behind an icon at the top left. The message box, tiles and "
     "cards all still fit — nothing is cut off or overlapping."),
    ("X-21", "On a phone", "Alia Al Suwaidi",
     "On the narrow screen, open the menu icon top left.",
     "A panel slides in with the person switcher at the top and the conversation list below."),

    ("X-22", "Keyboard only", "Alia Al Suwaidi",
     "From a fresh welcome screen, press Tab repeatedly until one of the four tiles is outlined, "
     "then press Enter.",
     "The tile activates, exactly as if clicked. Every tile should be reachable this way."),
    ("X-23", "Keyboard only", "Alia Al Suwaidi",
     "Tab through the page and watch the outline.",
     "Every button you can click shows a visible outline when it is selected. Nothing is invisible "
     "but still clickable."),

    ("X-24", "Long conversation", "Alia Al Suwaidi",
     "In ONE conversation, ask twelve questions in a row on different topics. On the twelfth, ask "
     'something that refers back to the first, e.g. "what was the first thing I asked you?"',
     "It still answers sensibly and has not lost the thread or started repeating itself."),

    ("X-25", "More documents", "Sultan Al Neyadi",
     "Upload the four files from demo/05-invoice-is-for-the-sibling--Shaikha-Al-Neyadi for Shaikha.",
     "The INVOICE is flagged, with a message about it being for a different child. Then fix it "
     "with the file in that folder's corrected/ and check it clears."),
    ("X-26", "More documents", "Khalifa Al Dhaheri",
     "Upload the four from demo/08-claimed-at-another-employer--Moza-Al-Dhaheri for Moza.",
     "It reports that the claim has already been made somewhere else. This one has NO corrected "
     "version — it is meant to be refused."),
    ("X-27", "More documents", "Noura Al Zaabi",
     "Upload the five files from demo/17-a-timetable-by-mistake--Ali-Al-Zaabi for Ali.",
     "It notices one file is a timetable rather than a required document, and says so, naming that "
     "file."),
]

# ── 3. Test data ─────────────────────────────────────────────────────────────

PEOPLE = [
    ("EMP001", "Alia Al Suwaidi", "Senior Consultant", "Maitha Al Mazrouei",
     "Khalifa, Hessa, Mohammed", "Enhanced — 45,000", "15 of 24, plus 3 carried over", "Passed"),
    ("EMP002", "Rashid Al Ketbi", "VP, Strategy & Operations", "Maitha Al Mazrouei",
     "nobody", "Standard — 25,000", "23 of 24, plus 5 carried over", "Passed"),
    ("EMP003", "Maitha Al Mazrouei", "Executive Director", "Board of Directors",
     "Alia, Rashid, Daniel, Noura, Sultan, Tariq, Elena", "Enhanced — 45,000", "11 of 26", "Passed"),
    ("EMP004", "Daniel Reed", "Director, Finance & Treasury", "Maitha Al Mazrouei",
     "Shamma", "Standard — 25,000", "15 of 21", "Passed"),
    ("EMP005", "Noura Al Zaabi", "Senior Specialist, Regulatory Affairs", "Maitha Al Mazrouei",
     "nobody", "Standard — 25,000", "26 of 26", "Passed"),
    ("EMP006", "Sultan Al Neyadi", "Manager, Client Delivery", "Maitha Al Mazrouei",
     "nobody", "Enhanced — 45,000", "18 of 26", "Passed"),
    ("EMP007", "Shamma Al Muhairi", "Facilities Supervisor", "Daniel Reed",
     "nobody", "NONE — no allowance", "10 of 14 (works 60%)", "STILL ON PROBATION"),
    ("EMP008", "Tariq Al Balushi", "Senior Strategy Specialist", "Maitha Al Mazrouei",
     "nobody", "Standard — 25,000", "21 of 26", "Passed (has left the company)"),
    ("EMP009", "Elena Costa", "VP, People & Culture", "Maitha Al Mazrouei",
     "nobody", "Enhanced — 45,000", "17 of 24", "Passed"),
    ("EMP010", "Khalifa Al Dhaheri", "Associate Consultant", "Alia Al Suwaidi",
     "nobody", "Standard — 25,000", "16 of 21", "Passed"),
    ("EMP011", "Hessa Al Shamsi", "Lead Consultant", "Alia Al Suwaidi",
     "nobody", "Enhanced — 45,000", "16 of 26", "Passed"),
    ("EMP012", "Mohammed Al Marri", "Associate Analyst", "Alia Al Suwaidi",
     "nobody", "Standard — 25,000", "18 of 21", "Passed"),
]

FACTS = [
    ("Carry-over limit", "10 days, must be used by 30 April", "Annual leave policy"),
    ("Standard annual leave", "21 days, rising to 24 / 26 / 30 with service", "Annual leave policy"),
    ("Sick leave total", "90 days — 15 full pay, 45 half pay, 30 unpaid", "Sick leave policy"),
    ("Medical certificate", "From the 3rd consecutive day, within 48 hours", "Sick leave policy"),
    ("Probation", "6 months, up to 12 for Grade 7 and above", "Probation policy"),
    ("Client meals", "AED 250 per head, including the employee", "Expenses policy"),
    ("Mileage", "AED 0.67 per kilometre", "Expenses policy"),
    ("Business class", "Grade 6 and above, flights of 5 hours or more", "Expenses policy"),
    ("Working from home", "Maximum 2 days a week, and 3 days a week in the office", "Remote work policy"),
    ("Gratuity / relocation", "NOT LOADED — the assistant should say it cannot answer", "—"),
]

PENDING = [
    ("Only one leave request is waiting for approval in the whole system.", "", ""),
    ("Request 17", "Hessa Al Shamsi — Annual Leave, 5 to 16 October 2026, 10 days",
     "Waiting on Alia Al Suwaidi"),
    ("If you approve it and want to test again",
     "Restart the backend (Ctrl+C in Terminal 1, then start it again).", ""),
]

DOCS = [
    ("Folder in hcs-11/documents/demo/", "Sign in as", "Child", "What it should show"),
    ("01-complete-and-clean--Luca-Costa", "Elena Costa", "Luca", "Everything fine"),
    ("02-still-missing-two--Amna-Al-Marri", "Mohammed Al Marri", "Amna", "Two documents missing"),
    ("14-photographed-at-night--Mariam-Al-Shamsi", "Hessa Al Shamsi", "Mariam",
     "Certificate unreadable — HAS a corrected version"),
    ("09-above-the-plan-limit--Emma-Reed", "Daniel Reed", "Emma", "Amount above the plan limit"),
    ("16-invoice-for-last-year--Omar-Al-Ketbi", "Rashid Al Ketbi", "Omar",
     "Invoice is for the wrong year — HAS a corrected version"),
    ("18-signed-by-the-other-parent--Saeed-Al-Mazrouei", "Maitha Al Mazrouei", "Saeed",
     "Declaration signed by the wrong parent — HAS a corrected version"),
    ("08-claimed-at-another-employer--Moza-Al-Dhaheri", "Khalifa Al Dhaheri", "Moza",
     "Already claimed elsewhere"),
    ("15-invoice-from-another-school--Sofia-Costa", "Elena Costa", "Sofia",
     "Invoice from a different school — HAS a corrected version"),
    ("05-invoice-is-for-the-sibling--Shaikha-Al-Neyadi", "Sultan Al Neyadi", "Shaikha",
     "Invoice is for the brother/sister — HAS a corrected version"),
    ("17-a-timetable-by-mistake--Ali-Al-Zaabi", "Noura Al Zaabi", "Ali",
     "A timetable sent instead of a certificate"),
    ("(20 folders in total — the rest are extra if you have time)", "", "", ""),
]

# ── 4. Known quirks ──────────────────────────────────────────────────────────

QUIRKS = [
    ("Do not report these", "Why", ""),
    ("Arabic text is left-aligned",
     "There is no Arabic button in the app and the page is fixed to English layout. The assistant "
     "still ANSWERS in Arabic — that part must work. Only the alignment is a known gap.", "Known"),
    ("No 'working on it' message when booking leave",
     "The progress messages were never wired up for the leave steps. The screen looks idle for "
     "up to a minute. Being fixed separately.", "Known"),
    ("No card after a manager approves or rejects",
     "The reply is plain text. The screen has no card built for that result yet.", "Known"),
    ("No pop-up after removing a document",
     "The pop-up component was never switched on. The list just refreshes.", "Known"),
    ("Confirm and Cancel buttons vanish if you scroll up",
     "Only the newest card keeps its buttons, on purpose, so you cannot confirm an old request "
     "by accident.", "By design"),
    ("An upload error mentions port 8001",
     "The message is wrong — the request goes to port 8000. Cosmetic.", "Known"),
    ("The calendar treats Saturday and Sunday as the weekend",
     "It should be Friday and Saturday for the UAE. Working-day counts may be off by a day or "
     "two. Worth confirming, already known.", "Known bug"),
    ("The calendar has no holidays outside 2026",
     "Navigate to 2027 and public holidays disappear.", "Known bug"),
    ("", "", ""),
    ("Data that contradicts the policy — not bugs in the assistant", "", ""),
    ("Shamma's leave entitlement",
     "Her record says 14 days; the policy would give 12.6 for her service and hours. The record "
     "is what the assistant reads.", "Test data"),
    ("Sultan's sick days do not add up",
     "His balance says 34 days used; his listed absences total 25. Do not test his sick figures.",
     "Test data"),
    ("Job titles do not match the grade table",
     "Alia is a Senior Consultant at Grade 8; the policy table says Senior Consultant is Grade 5. "
     "A question about her grade can answer two ways, both defensible.", "Test data"),
    ("School case statuses differ between the two systems",
     "This app keeps an old copy of the case list that nothing reads. Always trust what the "
     "upload window shows, not anything else.", "Test data"),
]


def build():
    book = Workbook()

    # Sheet 1
    start = book.active
    start.title = "Start here"
    write_header(start, ["", "Read this before you begin"], [34, 105])
    write_rows(start, SETUP, band_from=99)
    for index, (left, _) in enumerate(SETUP, start=2):
        if left and not SETUP[index - 2][1]:
            for column in (1, 2):
                cell = start.cell(row=index, column=column)
                cell.font = BOLD
                cell.fill = PatternFill("solid", fgColor=AMBER)
        start.cell(row=index, column=1).font = BOLD if left else BODY

    # Sheet 2
    tests = book.create_sheet("Test cases")
    write_header(
        tests,
        ["Test ID", "Area", "Sign in as", "What to do", "Expected result", "Result",
         "What actually happened"],
        [10, 20, 20, 58, 62, 14, 46],
    )
    write_rows(tests, [row + ("Not run", "") for row in CASES])
    choices = DataValidation(
        type="list", formula1='"Pass,Fail,Blocked,Not run"', allow_blank=False,
        showDropDown=False,
    )
    tests.add_data_validation(choices)
    choices.add(f"F2:F{len(CASES) + 1}")
    for row in range(2, len(CASES) + 2):
        tests.cell(row=row, column=6).alignment = WRAP_MID
        tests.cell(row=row, column=1).font = BOLD
    tests.auto_filter.ref = f"A1:G{len(CASES) + 1}"

    # Sheet 2b
    extra = book.create_sheet("Second pass")
    write_header(
        extra,
        ["Test ID", "Area", "Sign in as", "What to do", "Expected result", "Result",
         "What actually happened"],
        [10, 20, 20, 58, 62, 14, 46],
    )
    write_rows(extra, [row + ("Not run", "") for row in SECOND])
    more = DataValidation(
        type="list", formula1='"Pass,Fail,Blocked,Not run"', allow_blank=False,
        showDropDown=False,
    )
    extra.add_data_validation(more)
    more.add(f"F2:F{len(SECOND) + 1}")
    for row in range(2, len(SECOND) + 2):
        extra.cell(row=row, column=6).alignment = WRAP_MID
        extra.cell(row=row, column=1).font = BOLD
    extra.auto_filter.ref = f"A1:G{len(SECOND) + 1}"

    # Sheet 3
    data = book.create_sheet("Test data")
    row_at = 1

    def block(title, headers, rows, widths, fill):
        nonlocal row_at
        cell = data.cell(row=row_at, column=1, value=title)
        cell.font = Font(name="Calibri", size=12, bold=True, color="FF1F4E78")
        row_at += 1
        for column, (head, width) in enumerate(zip(headers, widths), start=1):
            head_cell = data.cell(row=row_at, column=column, value=head)
            head_cell.font = BOLD
            head_cell.fill = PatternFill("solid", fgColor=fill)
            head_cell.border = BOX
            head_cell.alignment = WRAP
            if data.column_dimensions[get_column_letter(column)].width or 0 < width:
                data.column_dimensions[get_column_letter(column)].width = width
        row_at += 1
        for entry in rows:
            for column, value in enumerate(entry, start=1):
                body_cell = data.cell(row=row_at, column=column, value=value)
                body_cell.font = BODY
                body_cell.alignment = WRAP
                body_cell.border = BOX
            row_at += 1
        row_at += 1

    block("The twelve people you can sign in as",
          ["ID", "Name", "Job title", "Their manager", "They manage",
           "Education plan", "Annual leave left", "Probation"],
          PEOPLE, [10, 22, 30, 22, 30, 22, 26, 22], GREEN)
    block("Policy answers you can rely on",
          ["Topic", "The correct answer", "Which policy"],
          FACTS, [10, 22, 30, 22], AMBER)
    block("The one request waiting for approval",
          ["", "", ""], PENDING, [10, 22, 30], AMBER)
    block("Document folders to test with", DOCS[0], DOCS[1:], [10, 22, 30, 22], GREEN)

    # Sheet 4
    quirks = book.create_sheet("Known quirks")
    write_header(quirks, ["What you will see", "Why it is not a bug to raise", "Type"],
                 [46, 80, 16])
    write_rows(quirks, QUIRKS)
    for index, (left, _, kind) in enumerate(QUIRKS, start=2):
        if not kind:
            for column in (1, 2, 3):
                cell = quirks.cell(row=index, column=column)
                cell.font = BOLD
                cell.fill = PatternFill("solid", fgColor=ROSE)

    book.save(OUTPUT)
    return len(CASES), len(SECOND)


if __name__ == "__main__":
    first, second_pass = build()
    print(f"wrote {OUTPUT.name} — {first} main + {second_pass} second pass "
          f"= {first + second_pass} tests")
