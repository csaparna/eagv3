const API_KEY = "AIzaSyDxj8hbOJdCIaq-heXc2k9T26-iUJh7bqQ";
const MODEL = "gemini-2.0-flash"; // Using Flash 2.0 as requested

async function generateLevel() {
    console.log("Generating level with Gemini...");
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent?key=${API_KEY}`;
    
    const prompt = `
        Generate a 2D platformer level for a 800x600 canvas in JSON format.
        Rules:
        1. Player starts at (50, 550).
        2. Provide 8-12 platforms. A platform is {x, y, w, h}.
        3. The goal {x, y} must be at the end of a challenging series of jumps.
        4. Difficulty: Hard (requires precision).
        5. Theme: Give it a cool name and primary/secondary colors.
        6. Return ONLY the JSON object.
        
        JSON Structure:
        {
          "platforms": [{"x": 0, "y": 580, "w": 800, "h": 20}, ...],
          "goal": {"x": 750, "y": 100},
          "theme": {"name": "Neon Heights", "primary": "#00ffcc", "bg": "#0a0a0a"}
        }
    `;

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000); // 10s timeout

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                contents: [{ parts: [{ text: prompt }] }]
            }),
            signal: controller.signal
        });

        clearTimeout(timeoutId);

        if (!response.ok) throw new Error(`API call failed with status ${response.status}`);

        const data = await response.json();
        
        if (!data.candidates || !data.candidates[0].content || !data.candidates[0].content.parts) {
            throw new Error("Invalid API response structure");
        }

        let rawText = data.candidates[0].content.parts[0].text;
        
        // Clean up markdown if Gemini returns it
        const jsonMatch = rawText.match(/\{[\s\S]*\}/);
        if (jsonMatch) rawText = jsonMatch[0];
        
        const levelData = JSON.parse(rawText);
        
        // Basic validation
        if (!levelData.platforms || !levelData.goal || !levelData.theme) {
            throw new Error("Incomplete level data in JSON");
        }

        console.log("Level generated successfully.");
        return levelData;
    } catch (error) {
        clearTimeout(timeoutId);
        console.error("Gemini Error:", error);
        
        // Fallback level if API fails or times out
        return {
            platforms: [
                {x: 0, y: 580, w: 200, h: 20},
                {x: 250, y: 500, w: 100, h: 20},
                {x: 400, y: 400, w: 100, h: 20},
                {x: 550, y: 300, w: 100, h: 20},
                {x: 700, y: 200, w: 100, h: 20}
            ],
            goal: {x: 750, y: 150},
            theme: {name: "Standard Quest", primary: "#6366f1", bg: "#0f172a"}
        };
    }
}
