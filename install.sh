#!/bin/bash
# BP1 Email Skill — Install to global Claude skills
set -e

SKILL_DIR="$HOME/.claude/skills/email"

if [ -d "$SKILL_DIR" ]; then
  echo "⚠️  $SKILL_DIR already exists."
  echo "    Overwrite? (y/N)"
  read -r answer
  if [ "$answer" != "y" ] && [ "$answer" != "Y" ]; then
    echo "Cancelled."
    exit 0
  fi
  rm -rf "$SKILL_DIR"
fi

mkdir -p "$SKILL_DIR"
cp -r email/* "$SKILL_DIR/"

echo ""
echo "✅ Email skill installed to $SKILL_DIR"
echo ""
echo "Next steps:"
echo "  1. Open Claude Code (in any directory)"
echo '  2. Say: "幫我設定 email" or "help me set up email"'
echo "  3. Claude will guide you through the rest"
echo ""
