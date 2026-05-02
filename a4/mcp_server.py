"""
MCP Server for academic paper research tools.
Uses FastMCP to expose search_semantic_scholar and log_paper_record as MCP tools.
Use 'fastmcp dev inspector mcp_server.py' to run the server and test the tools.
"""
import time
import json
import csv
import os
import requests
from fastmcp import FastMCP

mcp = FastMCP("Research Agent")


@mcp.tool()
def search_semantic_scholar(query: str, offset: int = 0, limit: int = 1) -> str:
    """Search Semantic Scholar for papers and return details including title, authors, tldr, citationCount, doi, and year."""
    query = '+'.join(query.split())
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={query}&offset={offset}&limit={limit}&fields=externalIds,authors,title,tldr,citationCount,year"

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}, timeout=10)
            if response.status_code == 429:
                wait = 2 ** (attempt + 1)
                print(f"  [429 rate limited, retrying in {wait}s... (attempt {attempt + 1}/{max_retries})]", flush=True)
                time.sleep(wait)
                continue
            response.raise_for_status()
            data = response.json()

            if 'data' not in data or not data['data']:
                return json.dumps({"error": "No results found."})

            results = []
            for item in data['data']:
                doi = item.get('externalIds', {}).get('DOI', 'Unknown DOI') if item.get('externalIds') else 'Unknown DOI'
                authors = ", ".join([a.get('name', '') for a in item.get('authors', [])]) if item.get('authors') else 'Unknown Authors'
                tldr = item.get('tldr', {}).get('text', 'No TLDR') if item.get('tldr') else 'No TLDR'

                results.append({
                    "title": item.get('title', 'Unknown Title'),
                    "authors": authors,
                    "tldr": tldr,
                    "citationCount": item.get('citationCount', 0),
                    "doi": doi,
                    "year": item.get('year', 0)
                })

            return json.dumps({"results": results})
        except Exception as e:
            if attempt == max_retries - 1:
                return json.dumps({"error": str(e)})
            time.sleep(2 ** (attempt + 1))

    return json.dumps({"error": "Max retries exceeded due to rate limiting (429)."})


@mcp.tool()
def log_paper_record(title: str, authors: str, doi: str, tldr: str, citation_count: int, year: int, csv_path: str = "papers.csv") -> str:
    """Add a paper's details to a CSV file as a separate row."""
    try:
        file_exists = os.path.isfile(csv_path)
        with open(csv_path, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(['Title', 'Authors', 'DOI', 'TLDR', 'Citation Count', 'Year'])
            writer.writerow([title, authors, doi, tldr, citation_count, year])
        return json.dumps({"status": "Success", "csv_file": csv_path})
    except Exception as e:
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    mcp.run()
