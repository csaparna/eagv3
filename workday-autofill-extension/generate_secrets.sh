#!/bin/bash

# This script generates a secrets.js file using the GEMINI_API_KEY environment variable.
# It ensures that the key is strictly available as an environment variable and not pushed to git.

if [ -z "$GEMINI_API_KEY" ]; then
  echo "Error: GEMINI_API_KEY environment variable is not set."
  echo "Please set it using: export GEMINI_API_KEY=\"your_api_key\""
  exit 1
fi

cat <<EOF > secrets.js
// This file is generated. DO NOT commit it to version control.
export const GEMINI_API_KEY = "${GEMINI_API_KEY}";
EOF

echo "Successfully generated secrets.js from environment variable."
