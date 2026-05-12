#!/usr/bin/env bash
INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // ""')
[[ "$CMD" =~ git\ commit ]] || exit 0  # only intercept commits

CWD=$(echo "$INPUT" | jq -r '.cwd // "."')
cd "$CWD" || exit 1

# Run the full pre-commit suite on staged files. exit 2 = block.
if ! pre-commit run --hook-stage commit --files $(git diff --cached --name-only) ; then
  echo "pre-commit failed. Fix the violations above before committing. Do NOT use --no-verify." >&2
  exit 2
fi
exit 0
