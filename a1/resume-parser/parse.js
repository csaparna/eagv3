const fs = require('fs/promises');
const path = require('path');
global.DOMMatrix = class DOMMatrix {};
const pdfParse = require('pdf-parse');

// Use same key as the extension uses
const apikey = "AIzaSyDxj8hbOJdCIaq-heXc2k9T26-iUJh7bqQ";

async function main() {
    console.log("Loading PDF...");
    const pdfPath = path.join(__dirname, '../data/resume.pdf');
    const dataBuffer = await fs.readFile(pdfPath);
    
    console.log("Parsing PDF text...");
    const data = await pdfParse(dataBuffer);
    const text = data.text;

    console.log("Extracted text length:", text.length, "characters");

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

    console.log("Sending to Gemini API...");
    const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${apikey}`, {
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
        const errText = await response.text();
        throw new Error(`Gemini API call failed: ${response.status} ${response.statusText} - ${errText}`);
    }

    const resData = await response.json();
    const resultText = resData.candidates[0].content.parts[0].text;
    
    // Parse into JSON to verify it's valid, then write it pretty
    const parsedJSON = JSON.parse(resultText);
    
    const dataOutputPath = path.join(__dirname, '../data/resume.json');
    const extOutputPath = path.join(__dirname, '../workday-autofill-extension/resume.json');
    
    await fs.writeFile(dataOutputPath, JSON.stringify(parsedJSON, null, 2));
    await fs.writeFile(extOutputPath, JSON.stringify(parsedJSON, null, 2));
    
    console.log(`Success! JSON securely saved to ${dataOutputPath} and bundled into the extension at ${extOutputPath}`);
}

main().catch(err => {
    console.error("Error running parser:");
    console.error(err);
    process.exit(1);
});
