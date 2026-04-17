// API_KEY is loaded from secrets.js
const MODEL = "gemini-flash-latest";

async function generateLevel() {
    console.log("Generating level with Gemini...");
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent?key=${API_KEY}`;
    
    const randomSeed = Math.random().toString(36).substring(7);
    const styles = ["vertical climb", "horizontal dash", "zig-zag maze", "precision drops", "sparse islands"];
    const layoutStyle = styles[Math.floor(Math.random() * styles.length)];

    const prompt = `
        Generate a 2D platformer level for an 800x600 canvas in JSON format.
        Seed: ${randomSeed}
        Layout Style Focus: ${layoutStyle}
        
        Rules for HARD difficulty:
        1. Player starts at (50, 550).
        2. Provide 10-15 platforms. A platform is {x, y, w, h}.
        3. The platform widths (w) MUST be very small (e.g., 20 to 50 pixels) to require precise landings.
        4. The horizontal and vertical gaps between platforms should be wide, stretching the limit of the player's jump.
        5. Provide 3 to 6 "lava" zones. Lava is {x, y, w, h}. Place these strategically under tricky jumps.
        6. The goal {x, y} must be at the very end of this challenging series of jumps.
        7. Theme: Cool name, primary color, secondary color, bg color.
        8. Return ONLY the JSON object.
        
        JSON Structure:
        {
          "platforms": [{"x": 0, "y": 580, "w": 100, "h": 20}, ...],
          "lava": [{"x": 200, "y": 580, "w": 100, "h": 20}, ...],
          "goal": {"x": 750, "y": 100},
          "theme": {"name": "Inferno Peak", "primary": "#00ffcc", "bg": "#0a0a0a"}
        }
    `;

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000); // 15s timeout

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                contents: [{ parts: [{ text: prompt }] }],
                generationConfig: {
                    temperature: 1.5, // High temperature for maximum variety
                    topK: 40,
                    topP: 0.95,
                    responseMimeType: "application/json"
                }
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
                {x: 0, y: 580, w: 100, h: 20},
                {x: 200, y: 500, w: 40, h: 20},
                {x: 350, y: 400, w: 40, h: 20},
                {x: 500, y: 300, w: 40, h: 20},
                {x: 650, y: 200, w: 80, h: 20}
            ],
            lava: [
                {x: 100, y: 580, w: 700, h: 20}
            ],
            goal: {x: 700, y: 150},
            theme: {name: "Hard Fallback", primary: "#6366f1", bg: "#0f172a"}
        };
    }
}
