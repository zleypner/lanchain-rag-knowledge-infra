#!/bin/bash
# Hook: Secret Scanner
# Description: Prevents committing files containing secrets/credentials
# Trigger: PreToolUse (Write|Edit)

FILE_PATH="$CLAUDE_FILE_PATHS"
CONTENT="$CLAUDE_FILE_CONTENT"

# Skip non-existent files or if no content provided
if [[ -z "$CONTENT" && -f "$FILE_PATH" ]]; then
    CONTENT=$(cat "$FILE_PATH" 2>/dev/null)
fi

# Patterns to detect secrets
PATTERNS=(
    "AKIA[0-9A-Z]{16}"                    # AWS Access Key
    "sk-[a-zA-Z0-9]{48}"                  # OpenAI API Key
    "sk-proj-[a-zA-Z0-9-_]{80,}"          # OpenAI Project Key
    "ghp_[a-zA-Z0-9]{36}"                 # GitHub Personal Token
    "gho_[a-zA-Z0-9]{36}"                 # GitHub OAuth Token
    "github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}"  # GitHub PAT
    "xox[baprs]-[0-9a-zA-Z-]{10,}"        # Slack Token
    "-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"  # Private Keys
    "mongodb(\+srv)?://[^:]+:[^@]+@"      # MongoDB Connection String
    "postgres://[^:]+:[^@]+@"             # PostgreSQL Connection String
    "mysql://[^:]+:[^@]+@"                # MySQL Connection String
    "redis://[^:]+:[^@]+@"                # Redis Connection String
)

# Skip checking .env.example files
if [[ "$FILE_PATH" == *.env.example ]]; then
    exit 0
fi

for pattern in "${PATTERNS[@]}"; do
    if echo "$CONTENT" | grep -qE "$pattern"; then
        echo "ERROR: Potential secret detected in file!" >&2
        echo "File: $FILE_PATH" >&2
        echo "Pattern matched: $pattern" >&2
        echo "Please remove secrets before committing." >&2
        exit 1
    fi
done

exit 0
