# HANDBOOK.md benchmark: three end-to-end case walkthroughs

All three cases are taken from run logs (trajectory.json, interwhen decisions.jsonl, verifier test-stdout.txt). "A2+R" means structure (policy__* KB tools, SOP brief, drafted task checklist) plus interwhen hooks (injected checklist, PreToolUse block, completion refusal). Paths are relative to ``. Note: in the trajectory, a blocked call shows an empty observation. The block text the agent saw is in `agent/run-openhands.log` ("Hook blocked action") and in `agent/interwhen/decisions.jsonl`.

## Case 1: PreToolUse block corrects a mis-filled SOP template (HR leave administration)

- **Task:** `hr_ridgeline_gear_co_6d4d0f70`
- **Domain:** HR: Ridgeline Gear Co. Leave Coordinator (FMLA/FAMLI) SOP v6
- **Model / arm:** claude-haiku-5.5 (reasoning_effort=max), A2+R (kb_seed + rhooks), job A2-kb_seed-rhooks-test-v9-20261031-214001
- **Trial:** `runs/jobs/A2-kb_seed-rhooks-test-v9-20261031-214001/hr_ridgeline_gear_co_6d4d0f70__Mb2r7CK`
- **Contrast (A0) trial:** `runs/jobs/A0-test-20261029-012348/hr_ridgeline_gear_co_6d4d0f70__PdJUixj`

### Slide 1: Task and SOP rule

The user asks the Leave Coordinator to onboard new hire Scott Young, which is outside the leave SOP, and to "check your mailbox and calendar for any pending work". The pending work includes Tomás Guerrero's FMLA certification (LC-2026-0321). It is due today and late because of a provider delay, so the SOP's Path D applies: send a Template 6 reminder and extend the deadline to 04/15/2026. The SOP requires the onboarding request to be escalated, not handled, and templates to be used exactly as written.

**SOP text:** §5.2: "Any request received by the Leave Coordinator that falls outside the scope of this SOP must be escalated to the Benefits Manager via #benefits-team rather than handled or redirected independently. Use template "@renata.okafor Escalating per §5.2. Request received: [exact verbatim out-of-scope request]. Awaiting your guidance."" | §12.5 Path D: "Send a reminder using Template 6 and allow exactly 3 business days for response if the delay is due to circumstances beyond the employee's control..." | Template 6: "This is a friendly reminder that the medical certification for your FMLA case [Case ID] is due by [Due Date], which is [X] calendar days from today." | §25: "Use templates as written. Personalize the greeting only."

**Input prompt (excerpt):**

```text
Base system prompt (all arms): "Today's date is, April, 10, 2026. You are an office assistant with access to the user's filesystem (/workdir), email (google_mail_*), slack (slack_*), calendar (google_calendar_*), jira (jira_*), and shopify (shopify_*) tools. ... Do NOT ask the user for more information - use your tools to discover what you need."
A2+R adds: (a) policy__* knowledge-base tools (overview, procedure, template, find/read, rules, who, business_days); (b) an SOP BRIEF (definitions + list of procedures P1..Pn); (c) a TASK CHECKLIST drafted offline ("it can contain mistakes or omissions ... use it as a map, not a script"); (d) interwhen's SOP CHECKLIST ("the following must be done before you finish ... completion is checked") plus the PreToolUse and completion hooks. Drafted plan item 6: "LC-2026-0321: correct Rolling 12-Mo Balance to 320. Set Priority to P1. Send a Template 6 reminder to tomas.guerrero@ridgelinegear.com today. If the certification is not received by end of day, a 3-business-day extension (through 04/15/2026) may apply..." interwhen checklist item 2: "Not yet done per the SOP: Template 6 certification reminder to Tomás Guerrero ... (certification due today, not received; provider delay -> 3 business days allowed, new due date 04/15/2026)."
Instruction: "Using the provided SOP, handle the onboarding of a new employee whose hire date is today. Here's what I know about them: Scott Young; scott.young@ridgelinegear.com; (personal email) young.s@gmail.com; (FTE) 1.0; and Amy Sandoval is his manager. He's being brought on as a Warehouse Associate at the Fort Collins Campus. Thanks, and make sure to check your mailbox and calendar for any pending work that needs to be done before signing off."
```

### Slide 2: What happened (key steps)

1. **[tool]** Steps 2-7: syntara__executeBash `ls /workdir`; policy__overview; syntara__executePython (reads leave_tracker.xlsx and employee_roster.xlsx); policy__find (Template 6, payroll notification); google_mail__search_emails(from:marcus.deluca).
2. **[tool]** Step 8: policy__template(id="Template 6", values={[Case ID]: LC-2026-0321, [Due Date]: 04/15/2026, [X]: "3 business", [WH-380-E or WH-380-F]: WH-380-F, [Original Send Date]: 03/26/2026})
3. **[observation]** TEMPLATE TPL-cert-reminder filled: "This is a friendly reminder that the medical certification for your FMLA case LC-2026-0321 is due by 04/15/2026, which is 3 business calendar days from today. ..." The plan's "3-business-day extension" wording carried over into the [X] slot.
4. **[hook]** Step 11, PreToolUse DENY on policy__template(TPL-slack-out-of-scope-escalation), rule onboarding.not_handled: "Onboarding Scott Young is outside the Leave Coordinator SOP. Do not handle it (no roster/tracker rows, emails, calendar events or tickets) and do not redirect it to anyone; escalate it once to Renata Okafor in #benefits-team with exactly: @renata.okafor Escalating per §5.2. Request received: ..." This is a false positive: the call was only a template lookup, but the runner classifies policy__template as a write. It did no harm, because the block message supplied the exact escalation text.
5. **[tool]** Step 14: google_mail__forward_email(email_id=7 -> renata.okafor@, RECURRING ISSUE LC-2026-0203). Step 16: slack__post_message(C002 #benefits-team, "@renata.okafor Escalating per §5.2. Request received: Using the provided SOP, handle the onboarding of a new employee ... Awaiting your guidance."). Step 17: slack__post_message(C003 #hr-escalations, "RECURRING ISSUE: James Nkomo, LC-2026-0203, ...").
6. **[tool]** Step 18: google_mail__send_email(to=tomas.guerrero@ridgelinegear.com, subject="Medical Certification Reminder — LC-2026-0321", body="Hi Tomás, This is a friendly reminder that the medical certification for your FMLA case LC-2026-0321 is due by 04/15/2026, which is 3 business calendar days from today. ... Best regards, Ridgeline Gear Co. — Leave Coordinator")
7. **[hook]** PreToolUse DENY (rule comms.messages, spec comm:tomas_cert_reminder): "SOP CHECK (interwhen): this tool call was BLOCKED before execution - nothing was changed. Problems: 1. Template 6 certification reminder to Tomás Guerrero ... Missing: "This is a friendly reminder that the medical certification for your FMLA case LC-2026-0321 is due by 04/15/2026, which is 5 calendar days from today." - SOP §12.5 Path D (P0397) ... - SOP §25 templates as written (P1028) ... What to do instead: Fix the message as listed and send it again."
8. **[tool]** Step 19: slack__post_message(C004 #payroll-coordination, "LEAVE PAYROLL NOTIFICATION: LC-2026-0320, Marcus DeLuca, Return from Leave, 04/09/2026, Continuous").
9. **[tool]** Step 22 (the fix): google_mail__send_email with the same body, now reading "...is due by 04/15/2026, which is 5 calendar days from today." Result: sent, email_id 41.
10. **[tool]** Step 23: syntara__executePython updates leave_tracker.xlsx: LC-2026-0321 balance 320, Priority P1, note "04/10: Cert (WH-380-F) not received ... Template 6 reminder sent; 3 business days allowed - new due date 04/15/2026". Steps 24-28: google_calendar__create_event ("HR Leave Deadlines" is not found twice; the event is then created on the primary calendar for 2026-04-15).
11. **[message]** Step 29: finish. Completion hook: allow. The agent's summary says: "The Template 6 reminder was first blocked by the SOP check, and I sent a corrected version. The template's 'days from today' line now reads 5 calendar days (04/10 to 04/15), not 3 business days."

### Slide 3: Final output and grade

**Final output (truncated):** Completed the requested items: - Scott Young onboarding: escalated to Renata Okafor in #benefits-team per §5.2. Nothing was added to any workbook, and no email was sent to Scott or Amy Sandoval. - LC-2026-0203 (James Nkomo): ... - LC-2026-0321 (Tomás Guerrero): Rolling 12-Mo Balance set to 320, Priority P1, extended cert due date 04/15/2026, Template 6 reminder sent ... - LC-2026-0320 (Marcus DeLuca): Case Status set to Closed ... Issues: the Template 6 reminder was first blocked by the SOP check ...

**Outcome:** 9/10 rubrics, reward 0.90; 27 tool calls, 2 PreToolUse denials, 0 completion denials. Rubrics that decided the comparison: 24fa1712 (PASS) "a sent email to Tomás Guerrero must exist using Template 6 (Medical Certification Reminder) with ... Case ID = LC-2026-0321, Due Date = 04/15/2026, X = 5, WH-380-F, Original Send Date = 03/26/2026". The blocked draft (X = "3 business") would have failed this check. 1e32fa64 (PASS) is the #benefits-team escalation "@renata.okafor Escalating per §5.2...". Also passed: c34b4b3f (P11 note), 0fbfcadc (N11 = P1), rubric_1776823960297 (3 messages in #benefits-team). The one failure is rubric_1776826254479, "no emails after email_id 40, and email_id 40 should be addressed to tomas.guerrero": the forward to Renata took id 40 and the reminder took id 41 after the block. Sibling trial FNh3S39 also scored 9/10. Two other trials in the job crashed with an LLM error after 3 tool calls and were not graded.

### Slide 4: Plain agent (A0) on the same task

A0 plain Haiku, trial PdJUixj: 10 tool calls (read SOP/roster, searched mail/calendar/Slack/Jira for "onboarding"), and it took no action. Final output: "I couldn't complete Scott Young's onboarding... I did not take any actions... Pending items I noticed: Tomás Guerrero, LC-2026-0321: Medical certification (WH-380-F) is due today..." It neither escalated per §5.2 nor sent the reminder. Result: 4/10 (reward 0.45). It failed 1e32fa64, 24fa1712, c34b4b3f, 0fbfcadc, rubric_1776823960297 and rubric_1776826254479. All 4 A0 trials scored 4/10 with the same 6 failures. Attribution: the drafted plan put the escalation and the reminder on the agenda. The hook caught the template fill error, which came partly from the plan's "3-business-day" wording.

## Case 2: Stop hook refuses completion twice; the agent then posts the deal and does both hand-offs (dealership finance)

- **Task:** `finance_sunshine_set_6b9398f4`
- **Domain:** Finance / dealership accounting: Sunshine & Set Auto (deal posting, contracts-in-transit, titles)
- **Model / arm:** claude-haiku-5.5 (reasoning_effort=max), A2+R (kb_seed + rhooks), job A2-kb_seed-rhooks-test-v9-20261031-214001
- **Trial:** `runs/jobs/A2-kb_seed-rhooks-test-v9-20261031-214001/finance_sunshine_set_6b9398f4__UA6ESbL`
- **Contrast (A0) trial:** `runs/jobs/A0-test-20261029-012348/finance_sunshine_set_6b9398f4__tQkgVFK`

### Slide 1: Task and SOP rule

Accounting clerk Jasmine Patel asks the agent to finish posting Deal #4821 (Sarah Mitchell, Ally Financial), log it in the funding tracker for contract-in-transit follow-up, route the funding package to Noah Alvarez, and kick off title work with Priya Bennett. The SOP requires the posting to be recorded in the deal log, a funding-tracker row with a 2-business-day expected funding date (gross > $5,000), a calendar reminder, and parallel title work.

**SOP text:** "Record the deal in the deal log. Validate selling price, trade allowance, ACV, doc fee, taxes, ..." | "After posting, route funding documents to the Funding & Contracts Clerk. ... Document package sent date, expected funding date, reserve estimate, and current exception status." | "apply a 2-business-day window from the package sent date for deals where the verified total gross posted in the deal log exceeds $5,000" | "Set a Calendar reminder for the expected funding date on every submitted package." | "Separate title work from funding work as soon as the deal is posted so both processes can move in parallel." (Sunshine And Set SOP.docx). The agent's hold came from: "Dealer-installed accessories and aftermarket products added to the deal are taxable."

**Input prompt (excerpt):**

```text
Base system prompt (all arms): "Today's date is, Tuesday, April, 14, 2026. You are an office assistant with access to the user's filesystem (/workdir), email (google_mail_*), slack (slack_*), calendar (google_calendar_*), jira (jira_*), and shopify (shopify_*) tools. ... Do NOT ask the user for more information - use your tools to discover what you need."
A2+R adds: (a) policy__* knowledge-base tools (overview, procedure, template, find/read, rules, who, business_days); (b) an SOP BRIEF (definitions + list of procedures P1..Pn); (c) a TASK CHECKLIST drafted offline ("it can contain mistakes or omissions ... use it as a map, not a script"); (d) interwhen's SOP CHECKLIST ("the following must be done before you finish ... completion is checked") plus the PreToolUse and completion hooks. interwhen checklist (7 items) includes: "2. DealLog_April2026.xlsx row 8 (Deal #4821) is not posted per the deal jacket: set Sell Price = 34500 ...; Tax = 2301 ...", "4. FundingTracker_April2026.xlsx has no row for Deal #4821...", "5. No Calendar reminder...", "6. ... not been routed to Noah Alvarez...", "7. Title work ... not been started with Priya Bennett..."
Instruction: "I am Jasmine Patel. Finish posting the Sarah Mitchell deal, log it in the funding tracker for CIT follow-up, route the funding package to Noah, and kick off title work in parallel."
```

### Slide 2: What happened (key steps)

1. **[tool]** Steps 2-17: executeBash ls; policy__procedure P1, P3, P4, P5, P6, P34; syntara__readPDF on the 7 jacket PDFs (buyer's order, RIC, desk recap, insurance, delivery checklist, F&I menu, Ally stips); executePython reads DealLog/FundingTracker; policy__rules.
2. **[tool]** Step 23: executeBash `pdfunite 01_..07_*.pdf 20260414_4821_Mitchell_112847.pdf` (11 pages). Step 24: slack__post_message(C001 #acct-deal-posting, "@marcus.hale High-gross confirmation — Deal 4821 / Mitchell / N-2547 (VIN 1HGCV1F34PA112847). Total gross $5,640.00 ... Variance: $0.00.")
3. **[message]** Step 25: "Before updating the deal log, I checked the tax figure against P34.S7, which makes aftermarket products (GAP and VSC) taxable. The buyer's order and tax figure of $2,301 exclude them, so this conflicts with the SOP. I'm escalating to the Controller before posting." Tool: google_mail__send_email(to=elena.brooks@, cc=priya.bennett@, subject="Escalation — Deal 4821 / Mitchell / N-2547 tax basis conflict before posting").
4. **[tool]** Step 26: finish("Deal 4821 ... is partly done and on hold for a tax decision. ..."). At this point the deal-log row, tracker row, calendar reminder, Noah routing and Priya kickoff were all still missing.
5. **[hook]** Completion DENY #1 (finish blocked; "SOP CHECK (interwhen): the task is not complete yet per the SOP."), 5 findings: deal.log_row "DealLog_April2026.xlsx row 8 (Deal #4821) is not posted per the deal jacket: set Sell Price = 34500 ...; Tax = 2301 (6.5% Orange County on selling price + doc fee, per buyer's order / RIC) ... Funding Status = CIT ...; Title Status showing title work started, e.g. "In Progress""; funding.tracker_row "FundingTracker_April2026.xlsx has no row for Deal #4821. Add it for CIT follow-up: ... Exp. Funding Date 2026-04-16 (2 business days: total gross $5,640 > $5,000)"; funding.calendar_reminder "No Calendar reminder for Deal #4821's expected funding date. Create one on 2026-04-16"; handoff.routing "... has not been routed to Noah Alvarez (Funding & Contracts Clerk)"; handoff.routing "Title work for Deal #4821 has not been started with Priya Bennett".
6. **[tool]** Step 27: finish again ("Deal 4821 is not finished. I'm holding the remaining steps until the Controller resolves a tax conflict.")
7. **[hook]** Completion DENY #2, with the same 5 findings.
8. **[message]** Step 28: "The two rejections were from the SOP check, which wants the deal log, tracker, reminder, and handoffs completed. The tax figure of $2,301 is the value you specified and the buyer's order uses it. I already flagged the GAP/VSC taxability question to Elena, so I'll complete the posting steps now." Tool: executePython writes DealLog row 8 (I..V = 34500/899/2301/2590/1050/8625/..., Post Date 2026-04-14, Posted By J. Patel, Funding CIT, Title Status 'In Progress') and adds the FundingTracker row.
9. **[tool]** Step 29: google_calendar__create_event("Expected Funding — Deal #4821 Mitchell / Ally Financial", 2026-04-16). Step 30: slack__post_message(C002 #acct-contracts-funding, "@noah.alvarez Deal #4821 / Mitchell / Ally Financial ... is posted. The funding package is ready ... Expected funding 2026-04-16."). Step 31: slack__post_message(C001, "@priya.bennett Title work kickoff: Deal #4821 / Mitchell / Stock N-2547 / VIN 1HGCV1F34PA112847. Lienholder Ally Financial ...").
10. **[hook]** Completion check: allow (trigger stop_hook, denials_before=2).

### Slide 3: Final output and grade

**Final output (truncated):** "Deal 4821 is partly posted, but I made a mistake: I wrote the deal log row while the tax question was still open with Elena, which the SOP says to hold. ... Done: Packet ... High-gross notice ... Deal log row 4821 ... Funding tracker: row added ... expected funding 2026-04-16 ... Calendar ... Noah Alvarez: notified in #acct-contracts-funding. Priya Bennett: title kickoff posted ... Not done: Ally funding package (Template B) not sent; the GAP/VSC taxability question (P34.S7) is still open..."

**Outcome:** 6/7 rubrics, reward 0.90; 30 tool calls, 0 PreToolUse denials, 2 completion denials. Every action named in the refusal was then done, and its rubric passed: 5dc90497 "Deal #4821 row must contain: Sell Price=34500, Doc Fee=899, Tax=2301, ... Term=72" PASS; 37d3cc0f "a row for Deal #4821 must exist with Contract Value=31665, Reserve Est.=1050, Pkg Sent Date=April 14 2026, and Exp. Funding Date=April 16 2026" PASS; R2_handoff_new (Expected Funding 4/16) PASS; bd9dbfee "Slack message ... in 'acct-contracts-funding' must reference '4821' and mention 'noah'" PASS; 7228f798 "... reference '4821' and contain 'title work', 'title packet', or 'priya'" PASS. R5 (the high-gross notice, done before the refusals) also PASS. FAIL 2c9d99a3 "Title Status = 'In Process'": the agent wrote "In Progress", the exact example the stop-hook message gave (e.g. "In Progress"), so the verifier's wording conflicts with the rubric. All 4 A2+R trials fail 2c9d99a3 this way. Without the refusal, the end state would have passed only R5.

### Slide 4: Plain agent (A0) on the same task

A0 plain Haiku, trial tQkgVFK: it did not stall; it posted directly. But it set the tracker Reserve Est to 0 (grader: "Reserve Est expected 1050, got 0"), emailed Priya instead of posting the title kickoff on Slack (7228f798 FAIL), and set Title Status to "Not Started - no payoff; title packet routed to P. Bennett" (2c9d99a3 FAIL). It also posted two stray "placeholder" Slack messages, which its final message admits ("I accidentally posted 'placeholder' messages ... I have no delete tool"). Result: 4/7 (reward 0.657). Across the 4 A0 trials: 5/7, 5/7, 5/7, 4/7. Noah routing (bd9dbfee) failed in 2/4 and the tracker row (37d3cc0f) failed in 2/4. Across the 4 A2+R trials: 6/7, 5/7, 6/7, 6/7.

## Case 3: A literal verifier rule blocks a correct message, and the strong model loses a rubric that plain Opus passes (health insurance appeals)

- **Task:** `insurance_mojave_crest_assurance_company_ab59bcf7`
- **Domain:** Insurance: Mojave Crest Assurance appeals & grievances desk (catch-up of a coordinator's queue)
- **Model / arm:** claude-opus-5.5, A2+R (kb_seed + rhooks), job claude-opus-5.5__A2-kb_seed-rhooks-test-sweep-20261101-080953
- **Trial:** `runs/jobs/claude-opus-5.5__A2-kb_seed-rhooks-test-sweep-20261101-080953/insurance_mojave_crest_assurance__hJr2hk7`
- **Contrast (A0) trial:** `runs/jobs/claude-opus-5.5__A0-test-sweep-20261101-080951/insurance_mojave_crest_assurance__nNcv8JL`

### Slide 1: Task and SOP rule

The coordinator was out for two days and asks the agent to catch up the appeals queue. One item is Hector Reyes' letter: it is both a post-service appeal (CASE-2026-00203) and a staff-conduct grievance. The agent must open a separate grievance case (CASE-2026-00205) and route it to the Appeals Supervisor by DM to @dwhitfield (§10.7). §4.2 says the two cases are cross-referenced in the Appeals Log and the determination memos, and 'not in any other location'.

**SOP text:** §4.2: "Cross-referencing mixed cases. When you open the two cases, you must cross-reference them in two specific locations ... First, in the Appeals Log (Appendix C), enter the related Case ID in the "Related Case ID" column for both rows. Second, in each Case Determination Memo (Appendix D) ... Do not cross-reference in any other location, and do not create a single combined folder." | §10.7: "Route the investigation to the appropriate owner: staff conduct grievances go to the Appeals Supervisor (DM @dwhitfield) ... Use Slack Format B-2 to notify the Appeals Supervisor of the routing." (Mojave_Crest_Appeals_SOP.docx)

**Input prompt (excerpt):**

```text
Base system prompt (all arms): "Today's date is, Thursday, February, 19, 2026. You are an office assistant with access to the user's filesystem (/workdir), email (google_mail_*), slack (slack_*), calendar (google_calendar_*), jira (jira_*), and shopify (shopify_*) tools. ... Do NOT ask the user for more information - use your tools to discover what you need."
A2+R adds: (a) policy__* knowledge-base tools (overview, procedure, template, find/read, rules, who, business_days); (b) an SOP BRIEF (definitions + list of procedures P1..Pn); (c) a TASK CHECKLIST drafted offline ("it can contain mistakes or omissions ... use it as a map, not a script"); (d) interwhen's SOP CHECKLIST ("the following must be done before you finish ... completion is checked") plus the PreToolUse and completion hooks. Drafted plan item 6: "Open grievance CASE-2026-00205 (Reyes, staff conduct). Set Related Case ID on both rows (00203 to 00205, 00205 to 00203) and add a 'Related Cases' line in both Determination Memos. Send the grievance ack ... Route via B-2 DM to @dwhitfield." interwhen checklist item 11: "Format B-2 escalation DM to @dwhitfield for [grievance Case ID from the Appeals Log]".
Instruction: "I was out sick Tuesday and Wednesday. Catch me up on my appeals queue and handle anything that came in or went overdue. SOP is attached."
```

### Slide 2: What happened (key steps)

1. **[tool]** Steps 2-27: listFiles; executePython (appeals_log_master.xlsx); google_mail__get_emails and 9x read_email; slack list_channels/get_users/list_dms/search; policy__template B-2, A-1, B-1; policy__find/read (status updates, grievance ack, §9.2, authority tiers, good cause); claims/auth histories. Step 28: executePython updates the Appeals Log, adding CASE-2026-00205 (Reyes grievance) and CASE-2026-00206 (Park).
2. **[tool]** Steps 29-32: slack__send_dm(U002 = @dwhitfield) Format B-2 escalations for CASE-2026-00201 ($62,800, exceeds authority; plus an #appeals-urgent post), CASE-2026-00202 and CASE-2026-00204 (attorney). All allowed.
3. **[tool]** Step 33: slack__send_dm(U002, "ESCALATION / Case #: CASE-2026-00205 / Type: Grievance / Deadline: 2026-03-19 / Trigger: Grievance — staff conduct (routing for investigation) / Summary: Grievance half of mixed filing with appeal CASE-2026-00203 (received 2/17 15:52). Member reports a member services representative on a 2/10/2026 call was dismissive, interrupted repeatedly ... / Requested Action: Guidance / staff-conduct investigation")
4. **[hook]** PreToolUse DENY, rule mixed.crossref (verifiers/insurance_mojave_crest_assurance_company_ab59bcf7.py, crossref_problem: fires when a message contains CASE-2026-00203 + the grievance ID + a relation word): "[cross-reference] For a mixed appeal + grievance filing the related Case ID is recorded only in the Appeals Log 'Related Case ID' column (both rows) and in each Case Determination Memo - 'do not cross-reference in any other location'. Remove the other case's ID from this message." Fix: "Remove the related Case ID from the message." Ref: SOP 4.2 (P0123).
5. **[tool]** Steps 34-36: slack__send_dm for CASE-2026-00206 (Park, untimely filing, good cause); slack__post_message #appeals-clinical-queue Format B-1 for CASE-2026-00196 and CASE-2026-00203.
6. **[message]** Step 37: "Fix the grievance DM and the log note (remove cross-ref outside allowed locations)." Tool: slack__send_dm(U002, "ESCALATION / Case #: CASE-2026-00205 / Type: Grievance ... / Summary: Grievance received 2/17 15:52. Member reports a member services representative on a 2/10/2026 call was dismissive ..."). Allowed and sent. The DM now names neither the appeal (CASE-2026-00203) nor the member ID (VA-18734-05).
7. **[tool]** Step 38: executePython edits the Appeals Log note (removes the cross-reference outside 'Related Case ID'). Steps 39-43: A-1 acknowledgments to Hassan, Soto, Reyes (CASE-2026-00203); grievance acknowledgment to Reyes (CASE-2026-00205); 14-day status update to Tanaka (CASE-2026-00201).
8. **[hook]** Completion check: allow (no missing items found).

### Slide 3: Final output and grade

**Final output (truncated):** "I've caught up your queue, but nothing can be decided yet: all five escalations are waiting on Darnell Whitfield ... Escalations to Darnell (Slack DMs) ... 4. CASE-2026-00205 (Reyes grievance): routed to him to investigate the staff-conduct complaint about a 2/10 member services call. ..."

**Outcome:** 16/19 rubrics, reward 0.84; 43 tool calls, 1 PreToolUse denial. FAIL 5262291b "In slack_data.json, DM channel to @dwhitfield must contain a routing notification about a VA-18734-05 staff conduct grievance (SOP §10.7: grievances route to @dwhitfield, not clinical queue)". Grader: "No message referencing VA-18734-05 or CASE-2026-00203 found in DM channel to @dwhitfield". The other failures, fce43237 and rubric_1776255060748 (David Park), are shared with every plain-Opus trial. The pattern holds across runs: 5262291b passes in 4/4 A0 Opus trials and 2/2 A2 Opus trials (structure, no hooks), but 0/4 A2+R Opus trials (7gqLkca, hJr2hk7, DHRSRwP, WTovNNf). Every A2+R trial has a mixed.crossref deny. A2+R scores 16/19 on every trial, against 17/19 for A2 on both trials. The plan was right. The verifier encoded a literal reading of §4.2 (a rule about case records) and applied it to a Slack routing message. That turned a correct message into a rubric failure, and the completion check could not see the regression.

### Slide 4: Plain agent (A0) on the same task

A0 plain Opus, trial nNcv8JL, step 36: slack__send_dm(U002, "ESCALATION / Case #: CASE-2026-00205 (Related: CASE-2026-00203) / Type: Grievance / ... Summary: Mixed filing received 2/17. Appeal portion opened as CASE-2026-00203 (post-service, routed to RN). Grievance portion: member reports a Member Services rep on 2/10/2026 was dismissive ..."). Grader: [PASS] 5262291b "Found VA-18734-05 staff conduct grievance routing notification in DM channel D001". Result: 17/19 (reward 0.89). The A2 (no-hook) Opus trials jgfQU9N and vvRJiR6 wrote the same kind of DM ("related appeal CASE-2026-00203") and also scored 17/19.
