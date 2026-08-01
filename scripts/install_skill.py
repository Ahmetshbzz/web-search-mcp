#!/usr/bin/env python3
import os
import shutil
from pathlib import Path

SKILL_NAME = "web-search-mcp"
SRC_SKILL = Path(__file__).resolve().parents[1] / ".agents" / "skills" / SKILL_NAME / "SKILL.md"

HOME = Path.home()

TARGET_DIRS = [
    HOME / ".gemini" / "config" / "skills" / SKILL_NAME,
    HOME / ".claude" / "skills" / SKILL_NAME,
    HOME / ".cursor" / "skills" / SKILL_NAME,
    HOME / ".cline" / "skills" / SKILL_NAME,
    HOME / ".opencode" / "skills" / SKILL_NAME,
    HOME / ".codex" / "skills" / SKILL_NAME,
]


def install_skills():
    if not SRC_SKILL.exists():
        print(f"[Error] Source skill file not found at {SRC_SKILL}")
        return

    print(f"Installing '{SKILL_NAME}' skill to all AI agent config roots...")
    for target_dir in TARGET_DIRS:
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            target_file = target_dir / "SKILL.md"
            shutil.copy2(SRC_SKILL, target_file)
            print(f"  ✓ Installed to: {target_file}")
        except Exception as exc:
            print(f"  ✗ Could not install to {target_dir}: {exc}")

    print("\nSkill installation completed successfully!")


if __name__ == "__main__":
    install_skills()
