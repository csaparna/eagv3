from ddgs import DDGS

# Initialize the search client
with DDGS() as ddgs:
    # Query for standard text results
    results = ddgs.text("Python programming", max_results=5)
    
    for r in results:
        print(f"Title: {r['title']}")
        print(f"URL: {r['href']}")
        print(f"Snippet: {r['body']}\n---")
