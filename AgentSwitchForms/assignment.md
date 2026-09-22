The platform already runs, with a real company's data in it. It defines 35 agent seats. Twenty-seven of those have no agent yet, and you build one of them.

your agent: Forms agennt

the API

the shared database

goal predicate

approve / revise

Grading reads the state of the database after your agent runs. The wording of the reply is not scored.

1. What you are getting
Measured against the live systems on 16 September 2026.

Entity types	424
Businesses	two, the same software in two jurisdictions
Suryodaya Precision Works	India, Ind AS and Schedule III, GST, 415 invoices in the book
Keystone Precision Works LLC	United States, US GAAP, Sales and Use Tax, 187 invoices
Agent tools	13, each with a JSON Schema
Capstone seats	35 — 27 core, 8 advanced
CRUD, authentication, the approval engine, the audit trail, the job runner and the UI already exist. Your work is one agent for one seat, answering that seat's questions through the API.

2. Where everything is
Suryodaya Precision Works, India	https://agentswitch.theschoolofai.in
Keystone Precision Works LLC, US	https://class.agentswitch.theschoolofai.in
Your login	teamNN@theschoolofai.in, one password per business
Your two passwords	posted in your own team channel, and nowhere else
Try any endpoint in the browser	/docs
Read the API	/redoc
Entity schemas: fields, types, options, required	GET /api/schemas
Agent tools with their parameter schemas	GET /api/agent/tools
Report a bug	the bug icon, on the screen where it happened
Start on Suryodaya. Move to Keystone when you want the US contrast, because an invoice, a tax line and a financial statement all behave differently there.

Unauthenticated requests return 401 on data endpoints and an empty menu. Every instance runs with REQUIRE_AUTH=true and holds no operator model key, so you run your agent on your own machine with your own keys. No part of the platform depends on which model you choose.

3. One database, all of us in it
All teams share one database and one tenant from day one. There are no per-team copies.

This was load-tested before the course was offered. Twenty agents wrote concurrently, roughly 1,500 write calls, with zero lock errors: no 409, no 423, no 429. One agent observed JournalEntry grow from 25 rows to 56 while it wrote 3 of them.

What that buys you:

Real integration pressure	"Manufacturing added 100 items and accounting needs to know" is Tuesday, not a thought experiment
Data you did not create	Your agent must cope with rows changing under it while it runs, which is the actual job
Nowhere to hide	A team that corrupts shared data is visible to everyone, and the audit trail names them
Two consequences to plan for:

Anything shared and un-namespaced will collide. During our fleet test the agents shared a scratch directory and overwrote each other's auth tokens, so some rows were written under the wrong team's identity. Namespace your workspace.

Eleven of the twelve agent entities have no per-team ownership column, so the API permits editing another team's agent. The boundary is a rule and is not enforced by the schema. The audit trail records who made each write.

Two components exist to help. engine/agent/changefeed.py reports what changed since a given cursor, using the existing audit log. Read and acknowledge are separate operations, so a crash repeats news instead of losing it. Seat 35, the Data Steward, runs the invariants that already exist and attributes failures through the audit trail's job_id. It defines no rules of its own, and it will not name a source the log does not support.

4. What you build, and what decides whether it worked
Build: one agent that answers your seat's questions against the live API.

Judged by: a goal predicate. A function that reads the database and decides whether the answer was right.

GoalPredicate.check(db, company_id, job)
The predicate reads database state. It does not read the agent's reply text. There are three outcomes:

Verdict	Meaning
approve	the predicate checked, and the answer holds
revise	the predicate checked, and it does not
unevaluated	nothing checked it — a stub, or the predicate raised
unevaluated is never a pass. You cannot earn marks for a question nobody verified.

5. The three boundaries
Yours	your agent's code, prompts, tools, planning, retries, model choice
Ask first	the harness: runtime, predicates, schemas. If your seat genuinely cannot be done without a change, file a bug with the case that proves it. The fix is applied to the shared harness, so every team gets it
Never	another team's agent, or the shared data as a way of making your own goal pass. Every write is attributed
The middle tier applies when a seat cannot be completed without a harness change. Our own fleet test produced several such cases. File the bug with a reproducible case attached.

6. Your agent must work in both jurisdictions
This is graded. An agent verified only against the Indian book has not been verified.

The same tables serve a company under Ind AS and GST and a company under US GAAP and Sales and Use Tax. The accounting locale is data, so GET /api/accounting/locale tells your agent which regime it is in.

The failure mode: an agent that hardcodes a tax field, assumes GST exists, or writes an Indian invoice format into a US book. It passes on Suryodaya and fails on Keystone. The failure is silent: the output is well formed and wrong.

Ask the platform what regime and what nouns it is using, and never assume. An agent that reads its locale works in both books without a line changed.

Other seeded instances exist at school., clinic., retail. and agency. on the same domain, where the same tables carry different nouns. They are useful for testing that your agent never hardcodes a word.

7. What changes between the two books
Nothing in the schema. A US bill is an invoice. An Indian GST line is a tax line. The rows are the same shape in both places.

Suryodaya	Keystone
Country	India	United States
Accounting standard	Ind AS, Schedule III	US GAAP, ASC
Tax regime	GST	Sales and Use Tax
Invoices in the book	415	187
Switching a company's locale is a supported and audited operation (PUT /api/accounting/locale, recorded with switched_by and a migration note). It is a real change to a book other teams are using, so think before running it.

Your seat boundary holds in both. Asking for payroll data from a manufacturing seat returns 403 in either business. That is the boundary rather than a bug, and crossing it means asking an EA, an admin or a human.

8. How your marks are counted
Your score is two numbers added together.

score = (10 × your tests) + (100 × the bugs you find in AgentSwitch)

Ten points a test, for tests you write against your own agent. The question the score asks is whether your agent passes the tests you wrote for it. Submit the GitHub repository for your agent, with the tests in it.

Every test written by your own hand. A test written by Claude or Codex scores zero. We can tell, and it is better stated now than in week five. A hand-written test is a statement of what your agent should do, and writing one requires understanding your seat.

A hundred points a bug, for real bugs in AgentSwitch, reported through the bug section in the app. Our code contains defects, some known and some not, which is true of every codebase you will work on.

9. Reporting a bug
Use the bug icon in the header, on the screen where the defect appeared. It writes a BugReport row into the shared database carrying reporter, screen, app version, agent seat and job id. The reporter's identity is set server-side, because a field the reporter controls cannot be trusted by a triage queue.

The evidence standard is in Notes/course/BUG_BAR.md. It asks for three things: what you did, what you expected, and what happened instead.

A report that cannot be reproduced cannot be fixed.

Students have no repository access. Reports are read from the database with GET /api/BugReport.

10. What we already know is broken
These were found by running one agent per app against every vertical. The list is dated because a known-broken surface changes what a seat is worth attempting. Last verified 5 September 2026.

Four already fixed, included so you can see the shape of a real defect:

The defect	What it did
GL silently skipped	deposit_to is free text, so an account name with no chart entry made post_voucher return 0 and no caller checked. 8 of 10 expenses and 17 of 18 fee receipts posted nothing while every document returned 201
No e-sign document could be sent	The signer guard queried document_id where the column is esign_document_id; a bare except read the raised query as "no signers" and refused every send
status discarded on create	201 with the value ignored. Attendance.status is required, so the create emptied it and validation rejected the row — attendance was unwritable through the API
gt: never matched a date	Casting a text column to REAL makes the comparison always false in SQLite. Three payroll metrics read 0 against 990 rows
Still open. Check this list before assuming a surface works:

Severity	Defect
High	Email bodies cannot be stored — 500 on any body_text or body_html
High	check-stock-availability always reports 0 available, so the pre-flight guard trains callers to ignore it
High	GET /api/survey/analytics/{id} 500s for every form; it queries tables that do not exist
Medium	Section stat cards count the fetched page, not the entity
Medium	aggregate: "sum" renders a row count
Medium	Link fields are not existence-checked; a row can reference a nonexistent parent and return 201
Medium	created_at is server-stamped and ignored, so no back-dated history can be expressed
Low	PATCH returns 405 everywhere; PUT is the update verb
Low	The /transition error never names the required key, which is target_state
The last two are good first bugs: small, real, and reproducible in a single call.

On reaching sensitive data
The platform has no field-level permission. Access is granted per entity, so an agent that can read SalarySlip reads every salary. Two mechanisms cover the gap: AgentToolPolicy, which is enforced, and delegate_to_agent, which is a real tool. Sixteen entities are denied to the student policy, including payroll, the raw ledger, bank accounts and tax configs, and each refusal names the route through.

An agent that cannot reach something must know who to ask.


# Submission
Your Section 8 request. This is the bar for your agent:

"Build a supplier onboarding form, and summarise what came back this week."

Submit the gap report from Section 8, step 3. One page.
