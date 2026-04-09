# Workday Auto-fill by Antigravity

A powerful Chrome Extension that automates the tedious process of filling out Workday job applications. It relies on an offline Node.js workflow to parse your PDF resume and bundle the data natively into the extension, allowing it to magically inject personal details, education history, and work experience into Workday forms perfectly.

## Features

- **Offline PDF Parsing**: Extracts text from your resume safely via a local Node.js script.
- **Smart Data Extraction**: Leverages Google Gemini (2.5 Flash) via standard CLI to pull out your resume data into a strictly structured `resume.json` schema.
- **Zero-Friction Extension**: The extension bundles your localized `resume.json` to be injected into Workday pages with a single click, completely removing any file uploads or API loading screens during the application process.

## Workflow: Updating Your Resume

Whenever you update your resume, you need to re-parse it so the extension holds the latest data:

1. Replace `/data/resume.pdf` with your newest resume.
2. Navigate to the parser directory:
   ```bash
   cd resume-parser
   ```
3. Run the parsing script:
   ```bash
   node parse.js
   ```
   *This script securely extracts your data using the Gemini API, evaluates it, and automatically injects the new `resume.json` dataset into both `/data/` and the `/workday-autofill-extension/` directory.*
4. Go to `chrome://extensions/` in your browser and click the **Reload button (↻)** on the *Workday Auto-fill by Antigravity* extension to recognize the new JSON bundle.

## Extension Setup Instructions

### 1. Add to Chrome (Developer Mode)

1. Open Google Chrome.
2. In the URL bar, go to `chrome://extensions/`.
3. Toggle on **Developer mode** in the top right corner.
4. Click **Load unpacked** in the top left corner.
5. Select the `workday-autofill-extension` directory.
6. The extension should now appear in your list of active extensions. Keep it pinned to your browser toolbar for quick access!

## Usage

1. Go to any job application hosted on Workday (`https://*.myworkdayjobs.com/*`).
2. You will see a small Antigravity Autofill widget in the bottom corner of the web page.
3. Click the **"Auto-fill Resume"** button on the widget OR open the Extension popup and click **"Auto-fill Application"**.
4. The extension will read your bundled `resume.json` instantly and meticulously populate the form fields.
5. **Review the fields**, ensure everything looks correct, and proceed with your application.

## Troubleshooting

- **Fields not filling:** Workday forms can vary greatly by employer. Our logic targets the most common `data-automation-id` tags dynamically. If it misses a field, manually fill it. 
- **Drop-down Menus**: Some Workday components like complex multi-selects or combo-boxes (e.g. Country / State) might require you to manually open the list and click the result even after the text is populated.
