// API_KEY is loaded from secrets.js
const MODEL = "gemini-3.1-flash-lite-preview";

async function generateLevel() {
    console.log("Generating level with Gemini...");
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent?key=${API_KEY}`;

    const styles = ["volcanic", "neon cyberpunk", "frozen tundra", "haunted forest", "underwater abyss", "sky kingdom", "lava caves", "crystal mines", "toxic swamp", "space station"];
    const chosenStyle = styles[Math.floor(Math.random() * styles.length)];

    // LLM only picks the theme — layout is generated algorithmically
    const prompt = `You are a game theme designer. Given the style "${chosenStyle}", respond with ONLY a JSON object with these three keys:
- "name": a short creative level name (2-4 words)
- "primary": a vivid hex color for platforms that fits the style
- "bg": a very dark hex color for the background that fits the style

Output ONLY raw JSON, no markdown, no explanation. Example:
{"name": "Neon Abyss", "primary": "#ff00ff", "bg": "#0a001a"}`;

    const schema = {
        type: "OBJECT",
        properties: {
            name: { type: "STRING" },
            primary: { type: "STRING" },
            bg: { type: "STRING" }
        },
        required: ["name", "primary", "bg"]
    };

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);

    let theme = null;

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                contents: [{ parts: [{ text: prompt }] }],
                generationConfig: {
                    temperature: 1.0,
                    maxOutputTokens: 100,
                    responseMimeType: "application/json",
                    responseSchema: schema
                }
            }),
            signal: controller.signal
        });

        clearTimeout(timeoutId);

        if (!response.ok) throw new Error(`API call failed with status ${response.status}`);

        const data = await response.json();

        if (data.candidates && data.candidates[0].content && data.candidates[0].content.parts) {
            let rawText = data.candidates[0].content.parts[0].text;
            const jsonMatch = rawText.match(/\{[\s\S]*\}/);
            if (jsonMatch) rawText = jsonMatch[0];
            const parsed = JSON.parse(rawText);
            if (parsed.name && parsed.primary && parsed.bg) {
                theme = parsed;
            }
        }
    } catch (error) {
        clearTimeout(timeoutId);
        console.warn("Theme API failed, using fallback theme:", error.message);
    }

    // Fallback theme if API fails
    if (!theme) {
        const fallbacks = [
            { name: "Neon Abyss", primary: "#00ffcc", bg: "#0a0a1a" },
            { name: "Inferno Peak", primary: "#ff6600", bg: "#1a0000" },
            { name: "Crystal Void", primary: "#aa88ff", bg: "#08001a" },
            { name: "Toxic Marsh", primary: "#aaff00", bg: "#001a00" }
        ];
        theme = fallbacks[Math.floor(Math.random() * fallbacks.length)];
    }

    // Generate the level layout algorithmically — guaranteed playable
    const levelData = buildLevel(theme, chosenStyle);
    console.log("Level generated:", theme.name);
    return levelData;
}
