#!/bin/bash
# Hook: Smart Commit
# Description: Enhances git workflow with pre-commit checks
# Trigger: PreToolUse (Bash) - when git commit is executed

COMMAND="$CLAUDE_BASH_COMMAND"

# Only check git commit commands
if ! echo "$COMMAND" | grep -qE "git commit"; then
    exit 0
fi

# Check if there are staged changes
STAGED=$(git diff --cached --name-only 2>/dev/null)
if [[ -z "$STAGED" ]]; then
    echo "WARNING: No staged changes detected." >&2
    echo "Did you forget to run 'git add'?" >&2
    exit 0
fi

# Check for common issues in staged files
STAGED_FILES=$(git diff --cached --name-only)

# Check for debug statements in code files
for file in $STAGED_FILES; do
    if [[ -f "$file" ]]; then
        case "$file" in
            *.py)
                if grep -n "print(" "$file" | grep -v "# noqa" | head -3; then
                    echo "WARNING: Found print() statements in $file" >&2
                fi
                if grep -n "breakpoint()" "$file" | head -1; then
                    echo "WARNING: Found breakpoint() in $file" >&2
                fi
                ;;
            *.js|*.ts|*.tsx|*.jsx)
                if grep -n "console\.log" "$file" | grep -v "// noqa" | head -3; then
                    echo "WARNING: Found console.log in $file" >&2
                fi
                if grep -n "debugger" "$file" | head -1; then
                    echo "WARNING: Found debugger statement in $file" >&2
                fi
                ;;
        esac
    fi
done

# Check for large files
for file in $STAGED_FILES; do
    if [[ -f "$file" ]]; then
        size=$(wc -c < "$file" 2>/dev/null | tr -d ' ')
        if [[ "$size" -gt 1000000 ]]; then
            echo "WARNING: Large file staged: $file ($(($size / 1024))KB)" >&2
        fi
    fi
done

exit 0
