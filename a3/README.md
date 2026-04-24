# Academic Paper Retrieval Agent

An automated AI agent powered by Google Gemini that organically searches for, downloads, and catalogues academic papers for local reading.

## Features

- **DOI Resolution:** Uses the Crossref API to seamlessly locate the valid Document Object Identifier (DOI) based securely on the paper's title and primary author.
- **Automated Sci-Hub Download:** Programmatically accesses Sci-Hub nodes, searches embedded `<object>` tags, Native PDF Responses, and download widgets to retrieve pure PDF files without human intervention.
- **Auto-Archiving:** Downloads papers automatically into a designated `/papers` directory with the LLM context-generating the best filenaming architecture.
- **CSV Cataloging:** Seamlessly manages a runtime journal in `papers.csv`, tracking references to all downloaded files natively.

## Requirements

- Python >= 3.12
- [uv](https://github.com/astral-sh/uv) for high-performance dependency management.

## Setup

1. Add your API credentials. At the root of your project, create a `.env` file containing your Gemini API key:
   ```env
   GEMINI_API_KEY=your_api_key_here
   GEMINI_MODEL=gemini-3-flash-preview
   ```

2. Sync and execute using `uv`:
   ```bash
   uv run agent.py
   ```

## How It Works

Modifying the behavior of the agent is completely natural-language driven. The engine sits at the bottom of `agent.py`. Adjust the input to fetch different journals explicitly:
```python
run_agent(
    "Save the paper on Crispr Cas9 by Doudna, download it, and document it."
)
```

The system will loop autonomously executing logic tools safely and effectively to honor your explicit research guidelines.
