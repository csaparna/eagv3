// background.js
let api_key = null;

async function loadSecrets() {
  try {
    const secrets = await import('./secrets.js');
    api_key = secrets.GEMINI_API_KEY;
  } catch (e) {
    console.warn("secrets.js not found. Make sure ./generate_secrets.sh was run.");
  }
}

// Load it immediately
loadSecrets();

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "ANALYZE_WITH_GEMINI") {
    if (!api_key) {
      sendResponse({ success: false, error: "API key not configured in background." });
      return true;
    }
    analyzeWithGemini(request.text)
      .then(data => sendResponse({ success: true, data }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    
    return true; // async
  }
});

async function analyzeWithGemini(text) {
  const prompt = `You are an expert ATS parser. Parse the following resume text and extract the Education and Experience sections into strict JSON format. 
DO NOT INCLUDE MARKDOWN FORMATTING (do not include \`\`\`json). Return raw JSON only.

The JSON MUST match this exact structure:
{
  "personal_info": {
    "firstName": "string",
    "lastName": "string",
    "addressLine1": "string",
    "city": "string",
    "state": "string",
    "postalCode": "string",
    "email": "string",
    "phone": "string"
  },
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
    let errBody = '';
    try {
        const errJson = await response.json();
        errBody = errJson.error && errJson.error.message ? errJson.error.message : JSON.stringify(errJson);
    } catch(e) {
        errBody = await response.text();
    }
    throw new Error(`API Error ${response.status}: ${errBody}`);
  }

  const data = await response.json();
  try {
      const resultText = data.candidates[0].content.parts[0].text;
      return JSON.parse(resultText);
  } catch (e) {
      throw new Error('Failed to parse Gemini response as JSON');
  }
}
