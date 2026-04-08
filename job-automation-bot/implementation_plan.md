# Automated Job Search and Auto-Apply Workflow

This implementation plan outlines the steps required to build a fully automated daily system that searches LinkedIn for specific roles, evaluates them against your resume, and attempts to auto-apply to the top matches.

## Core Architecture & Tech Stack

- **Language & Framework**: **Node.js** with **Playwright**. Node.js fits seamlessly with your existing Chrome extension codebase. Playwright offers strong browser isolation, letting us safely inject cookies and traverse complex SPAs (Single Page Applications) securely.
- **LLM Integration**: **Google Gemini API**. We will use `GEMINI_API_KEY` stored securely in your environment variables, mapping it using a generation script similar to your existing `generate_secrets.sh` to ensure it is never committed to Git.
- **Data Parsing**: `pdf-parse` (Node) to read `/home/aparna/eagv3/a1/data/resume.pdf` securely and extract the plain text.
- **Scheduling**: A local `node-cron` job, or a system-level `cron` task configured to run the index script at 10 AM daily.

---

## Proposed Implementation Steps

### Phase 1: Local Setup & Security
1. Initialize a new Node.js project directory.
2. Install necessary dependencies: `playwright`, `pdf-parse`, `@google/generative-ai`, and `dotenv`.
3. Create the automated secret loading script (`generate_secrets.sh`) to inject the `GEMINI_API_KEY` from the Linux shell environment.

### Phase 2: Resume Parsing & Matching Engine
1. **Load Resume**: Create a utility to read and parse the text from `../../data/resume.pdf`.
2. **LLM Prompting**: Define a strict system prompt using the Gemini API. It should evaluate a provided Job Description (JD) against your parsed resume and return a structured JSON response containing `{ "match_score": 85, "reasoning": "..." }`.

### Phase 3: Automated LinkedIn Scraper
1. **Auth & Browse**: Use Playwright to launch a persistent browser context pre-loaded with your active LinkedIn session cookies (keeps login secure and avoids captchas).
2. **Search Action**: Navigate to the LinkedIn jobs search endpoint with URL filters enabled for:
   - Keywords: `"ai context engineer"`
   - Location: `"Salt Lake City"` or `"Remote"`
   - Date Posted: `"Past 24 hours"`
3. **Data Extraction**: Extract the titles, application links, and the full JD text for the first page of recent postings.

### Phase 4: Job Evaluation & Auto-Apply Execution
1. **Evaluate**: Loop through the freshly scraped JDs, call the Gemini matching function, and filter for any where `match_score >= 70`.
2. **Prioritize**: Sort the matched jobs and select the Top 3 highest scores.
3. **Apply (Easy Apply)**:
   - For jobs supporting LinkedIn "Easy Apply", instruct Playwright to sequentially navigate the standard modal form, leveraging Gemini to answer any textual questions if required.
4. **Apply (External/Workday)**:
   - For external redirects like Workday, we can port over the data structures from your `workday-autofill-extension` to handle form filling programmatically in Playwright.

---

## Notes for Future Implementation

> [!TIP]
> **Getting Started**
> When you're ready to build this project later, you can start by confirming your `playwright` setup successfully captures and saves a screenshot of a logged-in LinkedIn session. 

> [!WARNING]
> **Scraping Limits**
> A daily check at 10 AM is a great strategy. Be cautious about running the search too aggressively multiple times an hour, as automated browsing limits might trigger a temporary pause on your LinkedIn account.
