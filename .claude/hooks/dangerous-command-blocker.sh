#!/bin/bash
# Hook: Dangerous Command Blocker
# Description: Blocks potentially destructive bash commands
# Trigger: PreToolUse (Bash)

COMMAND="$CLAUDE_BASH_COMMAND"

# List of dangerous patterns
DANGEROUS_PATTERNS=(
    "rm -rf /"
    "rm -rf /*"
    "rm -rf ~"
    "rm -rf \$HOME"
    "mkfs\."
    "dd if=.* of=/dev/"
    ":(){:|:&};:"                          # Fork bomb
    "chmod -R 777 /"
    "chown -R .* /"
    "> /dev/sda"
    "mv .* /dev/null"
    "wget .* | sh"
    "wget .* | bash"
    "curl .* | sh"
    "curl .* | bash"
    "shutdown"
    "reboot"
    "init 0"
    "init 6"
    "poweroff"
    "halt"
    "git push.*--force.*main"
    "git push.*--force.*master"
    "git push.*-f.*main"
    "git push.*-f.*master"
    "git reset --hard.*origin"
    "DROP DATABASE"
    "DROP TABLE"
    "TRUNCATE TABLE"
    "DELETE FROM .* WHERE 1"
    "npm publish"
    "pip upload"
)

for pattern in "${DANGEROUS_PATTERNS[@]}"; do
    if echo "$COMMAND" | grep -qiE "$pattern"; then
        echo "ERROR: Potentially dangerous command blocked!" >&2
        echo "Command: $COMMAND" >&2
        echo "Pattern matched: $pattern" >&2
        echo "If this is intentional, please run manually." >&2
        exit 1
    fi
done

exit 0
