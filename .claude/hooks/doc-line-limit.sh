#!/bin/bash
# Hook: Documentation Line Limit
# Description: Ensures documentation files (.md) don't exceed 500 lines
# Trigger: PostToolUse (Write|Edit)

FILE_PATH="$CLAUDE_FILE_PATHS"
MAX_LINES=500

if [[ "$FILE_PATH" == *.md ]]; then
    lines=$(wc -l < "$FILE_PATH" 2>/dev/null | tr -d ' ' || echo 0)
    if [ "$lines" -gt "$MAX_LINES" ]; then
        echo "ERROR: Documentation files should not exceed $MAX_LINES lines." >&2
        echo "File: $FILE_PATH" >&2
        echo "Current lines: $lines" >&2
        exit 1
    fi
fi

exit 0
