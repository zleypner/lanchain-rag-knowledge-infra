#!/bin/bash
# Hook: Conventional Commits
# Description: Validates commit messages follow conventional commits format
# Trigger: PostToolUse (Bash) - when git commit is executed

COMMAND="$CLAUDE_BASH_COMMAND"
OUTPUT="$CLAUDE_TOOL_OUTPUT"

# Only check git commit commands
if ! echo "$COMMAND" | grep -qE "git commit"; then
    exit 0
fi

# Extract commit message from command
COMMIT_MSG=""
if echo "$COMMAND" | grep -qE '\-m ["\x27]'; then
    COMMIT_MSG=$(echo "$COMMAND" | sed -n 's/.*-m ["\x27]\([^"\x27]*\)["\x27].*/\1/p')
fi

# If we couldn't extract message, try getting from last commit
if [[ -z "$COMMIT_MSG" ]]; then
    COMMIT_MSG=$(git log -1 --pretty=%B 2>/dev/null | head -1)
fi

if [[ -z "$COMMIT_MSG" ]]; then
    exit 0
fi

# Conventional commit pattern
# type(scope)?: description
PATTERN="^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([a-zA-Z0-9_-]+\))?: .+"

if ! echo "$COMMIT_MSG" | grep -qE "$PATTERN"; then
    echo "WARNING: Commit message doesn't follow conventional commits format." >&2
    echo "Message: $COMMIT_MSG" >&2
    echo "" >&2
    echo "Expected format: type(scope)?: description" >&2
    echo "Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert" >&2
    echo "" >&2
    echo "Examples:" >&2
    echo "  feat(auth): add login functionality" >&2
    echo "  fix: resolve memory leak in parser" >&2
    echo "  docs(readme): update installation steps" >&2
    # Warning only, don't block
    exit 0
fi

exit 0
