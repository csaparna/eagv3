"""
Domain Explorer for Forms Seat (Seat 25).
Fetches schemas and MCP tools available to Seat 25 using standard library urllib without printing credentials or tokens.
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent

def http_get(url, headers):
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))

def http_post(url, headers, data):
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))

def fetch_domain_data():
    base_url = os.environ.get("AS")
    token = os.environ.get("TOKEN")

    if not base_url or not token:
        print("Missing base URL or token in environment.", file=sys.stderr)
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # 1. Who am I (roles, allowed_apps)
    print("Fetching /api/auth/me...")
    try:
        status, me_data = http_get(f"{base_url}/api/auth/me", headers)
        safe_me = {
            "roles": me_data.get("roles"),
            "allowed_apps": me_data.get("allowed_apps"),
            "company_id": me_data.get("company_id"),
            "team": me_data.get("team"),
        }
        with open(OUTPUT_DIR / "seat_info.json", "w") as f:
            json.dump(safe_me, f, indent=2)
        print(f"Seat Info saved: roles={safe_me.get('roles')}, apps={safe_me.get('allowed_apps')}")
    except Exception as e:
        print(f"Error fetching auth/me: {e}", file=sys.stderr)

    # 2. Accounting Locale
    print("Fetching /api/accounting/locale...")
    try:
        status, locale_data = http_get(f"{base_url}/api/accounting/locale", headers)
        with open(OUTPUT_DIR / "accounting_locale.json", "w") as f:
            json.dump(locale_data, f, indent=2)
        print(f"Accounting Locale saved: {locale_data}")
    except Exception as e:
        print(f"Error fetching locale: {e}", file=sys.stderr)

    # 3. MCP Tools List
    print("Fetching MCP tools/list...")
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
        status, resp = http_post(f"{base_url}/api/mcp", headers, payload)
        tools = resp.get("result", {}).get("tools", [])
        with open(OUTPUT_DIR / "mcp_tools.json", "w") as f:
            json.dump(tools, f, indent=2)
        tool_names = [t.get("name") for t in tools]
        print(f"MCP tools fetched: {len(tools)} tools total.")
        forms_tools = [name for name in tool_names if any(k in name.lower() for k in ["form", "survey", "response", "consent", "supplier", "vendor"])]
        print(f"Forms-related MCP tools ({len(forms_tools)}): {forms_tools}")
    except Exception as e:
        print(f"Error fetching MCP tools: {e}", file=sys.stderr)

    # 4. Schemas
    print("Fetching /api/schemas...")
    try:
        status, all_schemas = http_get(f"{base_url}/api/schemas", headers)
        
        # Save raw schemas first so we never lose the raw server response
        with open(OUTPUT_DIR / "raw_schemas.json", "w") as f:
            json.dump(all_schemas, f, indent=2)
        print("Raw schemas saved to raw_schemas.json")

        forms_keywords = ["form", "survey", "response", "consent", "supplier", "vendor", "party", "lead"]
        
        # Helper to check if a string matches any keyword
        def matches_keyword(name):
            if not isinstance(name, str):
                return False
            name_lower = name.lower()
            return any(kw in name_lower for kw in forms_keywords)

        relevant_schemas = {}

        # Inspect nested format
        print(f"all_schemas type: {type(all_schemas).__name__}")

        def find_entities(obj, path=""):
            if isinstance(obj, dict):
                # Check if this dict itself looks like an entity schema (has 'fields', 'properties', 'columns', or 'type')
                # and path or a name field matches our keywords
                name = obj.get("name") or obj.get("entity") or obj.get("title") or obj.get("table") or obj.get("id")
                has_schema_structure = any(k in obj for k in ["fields", "properties", "columns", "type", "attributes"])

                if (name and matches_keyword(str(name)) and has_schema_structure):
                    relevant_schemas[str(name)] = obj

                for k, v in obj.items():
                    current_path = f"{path}.{k}" if path else k
                    if matches_keyword(k):
                        if isinstance(v, dict) and any(sk in v for sk in ["fields", "properties", "columns", "type", "attributes"]):
                            relevant_schemas[k] = v
                        elif isinstance(v, dict):
                            # It might be a group of entities under an app like 'forms': {'Form': {...}, ...}
                            for sub_k, sub_v in v.items():
                                if isinstance(sub_v, dict) and any(sk in sub_v for sk in ["fields", "properties", "columns", "type", "attributes"]):
                                    relevant_schemas[sub_k] = sub_v
                                elif matches_keyword(sub_k):
                                    relevant_schemas[sub_k] = sub_v
                                else:
                                    # Include all entities under 'forms' app
                                    if "form" in k.lower():
                                        relevant_schemas[sub_k] = sub_v
                    # Recurse down
                    if isinstance(v, (dict, list)):
                        find_entities(v, current_path)

            elif isinstance(obj, list):
                for item in obj:
                    if isinstance(item, dict):
                        name = item.get("name") or item.get("entity") or item.get("title") or item.get("table") or item.get("id")
                        if name and matches_keyword(str(name)):
                            relevant_schemas[str(name)] = item
                        else:
                            find_entities(item, path)

        find_entities(all_schemas)

        with open(OUTPUT_DIR / "forms_schemas.json", "w") as f:
            json.dump(relevant_schemas, f, indent=2)
        print(f"Extracted {len(relevant_schemas)} relevant schemas into forms_schemas.json: {list(relevant_schemas.keys())}")
    except Exception as e:
        print(f"Error fetching schemas: {e}", file=sys.stderr)


if __name__ == "__main__":
    fetch_domain_data()

