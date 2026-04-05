// popup.js
let api_key = null;
try {
  const secrets = await import('./secrets.js');
  api_key = secrets.GEMINI_API_KEY;
} catch (e) {
  console.warn("secrets.js not found. User has not generated it yet.");
}

// Setup PDF.js worker
pdfjsLib.GlobalWorkerOptions.workerSrc = 'pdf.worker.js';

const pdfUpload = document.getElementById('pdfUpload');
const fileName = document.getElementById('fileName');
const autofillBtn = document.getElementById('autofillBtn');
const statusDiv = document.getElementById('status');

let extractedText = '';

pdfUpload.addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (!file) {
    fileName.textContent = 'No file chosen';
    autofillBtn.disabled = true;
    return;
  }
  
  fileName.textContent = file.name;
  setStatus('Extracting text from PDF...', 'status-loading');
  autofillBtn.disabled = true;

  try {
    const arrayBuffer = await file.arrayBuffer();
    const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
    
    let text = '';
    for (let i = 1; i <= pdf.numPages; i++) {
      const page = await pdf.getPage(i);
      const content = await page.getTextContent();
      const pageText = content.items.map(item => item.str).join(' ');
      text += pageText + '\n';
    }
    extractedText = text;
    setStatus('PDF parsed successfully! Ready to autofill.', 'status-success');
    autofillBtn.disabled = false;
  } catch (err) {
    console.error(err);
    setStatus('Error extracting PDF text. See console.', 'status-error');
  }
});

autofillBtn.addEventListener('click', async () => {
  if (!api_key) {
    setStatus('Error: secrets.js is missing or API key is not set. Run generate_secrets.sh.', 'status-error');
    return;
  }

  setStatus('Analyzing with Gemini AI...', 'status-loading');
  autofillBtn.disabled = true;

  try {
    const parsedData = await analyzeWithGemini(extractedText);
    setStatus('Sending data to Workday form...', 'status-loading');

    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    
    if (!tab) {
        throw new Error('No active tab found.');
    }

    try {
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ['content.js']
      });
    } catch(err) {
        // May already be injected or not allowed on this page
        console.warn('Script execution warning:', err);
    }
    
    // Give content script a tiny bit of time if just injected
    setTimeout(() => {
        chrome.tabs.sendMessage(tab.id, {
            action: 'FILL_WORKDAY_FORM',
            data: parsedData
        }, (response) => {
            if (chrome.runtime.lastError) {
               setStatus('Error: Could not connect to page. Are you on a Workday site?', 'status-error');
               autofillBtn.disabled = false;
               return;
            }
            if (response && response.success) {
               setStatus('Autofill complete! Please review the form.', 'status-success');
            } else {
               setStatus('Autofill finished but encountered warnings. Please review.', 'status-success');
            }
            autofillBtn.disabled = false;
        });
    }, 200);

  } catch (err) {
    console.error(err);
    setStatus('Error during AI processing: ' + err.message, 'status-error');
    autofillBtn.disabled = false;
  }
});

function setStatus(text, className) {
  statusDiv.textContent = text;
  statusDiv.className = 'status-container ' + className;
}

async function analyzeWithGemini(text) {
  const prompt = `You are an expert ATS parser. Parse the following resume text and extract the Education and Experience sections into strict JSON format. 
DO NOT INCLUDE MARKDOWN FORMATTING (do not include \`\`\`json). Return raw JSON only.

The JSON MUST match this exact structure:
{
  "education": [
    {
      "school": "University Name",
      "degree": "Bachelor, Master, etc.",
      "major": "Field of Study",
      "startMonth": "MM", 
      "startYear": "YYYY",
      "endMonth": "MM",
      "endYear": "YYYY"
    }
  ],
  "experience": [
    {
      "title": "Job Title",
      "company": "Company Name",
      "location": "City, State",
      "startMonth": "MM",
      "startYear": "YYYY",
      "endMonth": "MM",
      "endYear": "YYYY",
      "description": "Full description of responsibilities"
    }
  ]
}

If a field is not found, leave it as an empty string "". Use 2-digit format for months (e.g. 01 for January).

 Resume text:
 ${text.substring(0, 8000)}
 `;

  const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${api_key}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contents: [{ parts: [{ text: prompt }] }],
      generationConfig: {
          responseMimeType: "application/json"
      }
    })
  });

  if (!response.ok) {
    throw new Error('Gemini API call failed: ' + response.statusText);
  }

  const data = await response.json();
  try {
      const resultText = data.candidates[0].content.parts[0].text;
      return JSON.parse(resultText);
  } catch (e) {
      throw new Error('Failed to parse Gemini response as JSON');
  }
}
