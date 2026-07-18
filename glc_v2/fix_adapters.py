import glob, re, os

for path in glob.glob("glc/channels/catalogue/*/adapter.py"):
    with open(path, "r") as f:
        content = f.read()

    # Remove the import line
    content = re.sub(r'from glc\.security\.pairing import.*get_pairing_store.*\n', '', content)

    # Replace owners lookup with empty list
    content = re.sub(r'owners?(_ids)? = \[.*?in get_pairing_store\(\)\.owners\(.*?\)\]', 'owners = []', content)

    # Replace lookup with None
    content = re.sub(r'rec = get_pairing_store\(\)\.lookup\(.*?\)', 'rec = None', content)
    
    with open(path, "w") as f:
        f.write(content)

print("Fixed adapters")
