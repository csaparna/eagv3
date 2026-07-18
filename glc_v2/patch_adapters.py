import os, glob, re

for path in glob.glob("glc/channels/catalogue/*/adapter.py"):
    with open(path, "r") as f:
        content = f.read()
    
    # Remove imports
    content = re.sub(r'from glc\.security\.pairing import.*get_pairing_store.*\n', '', content)
    
    # Remove user_handle lookup block
    content = re.sub(r'# Get handle/username\s*if not user_handle:\s*store = get_pairing_store\(\)\s*rec = store\.lookup\(self\.name,\s*channel_user_id\)\s*user_handle = rec\.user_handle if rec else channel_user_id', '', content)
    
    # Remove public channel allowlist check block
    content = re.sub(r'# Allowlist check for stranger in public channel\s*if self\.config\.get\("is_public_channel"\):\s*owners = \[.*?\]\s*is_allowed, _ = allowed\([\s\S]*?if not is_allowed:\s*return None', '', content)

    # Some adapters might have different whitespace or variables, let's do a more robust sweep if needed
    with open(path, "w") as f:
        f.write(content)

print("Patched adapters.")
