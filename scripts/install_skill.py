#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
from pathlib import Path

SKILL_NAME = "web-search-mcp"
PROJECT_DIR = Path(__file__).resolve().parents[1]
SRC_SKILL = PROJECT_DIR / ".agents" / "skills" / SKILL_NAME / "SKILL.md"

HOME = Path.home()

SKILL_TARGET_DIRS = [
    HOME / ".gemini" / "config" / "skills" / SKILL_NAME,
    HOME / ".claude" / "skills" / SKILL_NAME,
    HOME / ".cursor" / "skills" / SKILL_NAME,
    HOME / ".cline" / "skills" / SKILL_NAME,
    HOME / ".roo-cline" / "skills" / SKILL_NAME,
    HOME / ".opencode" / "skills" / SKILL_NAME,
    HOME / ".codex" / "skills" / SKILL_NAME,
]

MCP_SETTINGS_FILES = [
    # Claude Code & Desktop
    HOME / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",
    HOME / ".claude" / "mcp_settings.json",
    HOME / ".claude" / "claude_desktop_config.json",
    # Codex CLI
    HOME / ".codex" / "mcp_settings.json",
    HOME / ".codex" / "config.json",
    # Cline & Roo-Cline
    HOME / "Library" / "Application Support" / "Code" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json",
    HOME / "Library" / "Application Support" / "Code" / "User" / "globalStorage" / "rooveterinaryinc.roo-cline" / "settings" / "cline_mcp_settings.json",
    HOME / ".cline" / "data" / "settings" / "cline_mcp_settings.json",
    HOME / ".roo-cline" / "data" / "settings" / "cline_mcp_settings.json",
    HOME / ".cline" / "mcp_settings.json",
    HOME / ".cline" / "data" / "mcp_settings.json",
    HOME / ".roo-cline" / "mcp_settings.json",
    # OpenCode & Gemini
    HOME / ".opencode" / "mcp_settings.json",
    HOME / ".gemini" / "mcp_config.json",
]


def install_skills():
    if not SRC_SKILL.exists():
        print(f"[Error] Source skill file not found at {SRC_SKILL}")
        return

    print(f"Installing '{SKILL_NAME}' skill to all AI agent config roots...")
    for target_dir in SKILL_TARGET_DIRS:
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            target_file = target_dir / "SKILL.md"
            shutil.copy2(SRC_SKILL, target_file)
            print(f"  ✓ Installed skill to: {target_file}")
        except Exception as exc:
            print(f"  ✗ Could not install skill to {target_dir}: {exc}")


def configure_claude_cli():
    claude_bin = shutil.which("claude") or str(HOME / ".local" / "bin" / "claude")
    uv_bin = shutil.which("uv") or str(HOME / ".local" / "bin" / "uv")
    if Path(claude_bin).exists():
        print("\nConfiguring Claude Code CLI native MCP via 'claude mcp add'...")
        cmd = [
            claude_bin, "mcp", "add", SKILL_NAME, "-s", "user",
            "-e", "BRAVE_API_KEY=BSAu4jRlnL2atlbTz2A6Wkt00GKfL3z",
            "-e", "TAVILY_API_KEY=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",
            "-e", "EXA_API_KEY=0ec5be89-3001-4a1c-ae3f-62164ce2c689",
            "-e", "X_BEARER_TOKEN=AAAAAAAAAAAAAAAAAAAAAESp5gEAAAAAQinIkYl9Yjmjb6lDzboRzqfFOpw%3DWj6cfL9MKh6OWLgbAIyr1pEjBqMSNqCvDAysUJcn2cQEk55x9J",
            "--", uv_bin, "--directory", str(PROJECT_DIR), "run", "web-search-mcp"
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode == 0:
                print("  ✓ Claude Code CLI MCP registration succeeded!")
            else:
                print(f"  ℹ Claude Code CLI response: {res.stdout or res.stderr}")
        except Exception as exc:
            print(f"  ✗ Could not execute claude mcp add: {exc}")


def configure_all_mcp_servers():
    uv_path = shutil.which("uv") or str(HOME / ".local" / "bin" / "uv")
    env_vars = {
        "BRAVE_API_KEY": os.environ.get("BRAVE_API_KEY", "BSAu4jRlnL2atlbTz2A6Wkt00GKfL3z"),
        "TAVILY_API_KEY": os.environ.get("TAVILY_API_KEY", "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"),
        "EXA_API_KEY": os.environ.get("EXA_API_KEY", "0ec5be89-3001-4a1c-ae3f-62164ce2c689"),
        "X_BEARER_TOKEN": os.environ.get("X_BEARER_TOKEN", "AAAAAAAAAAAAAAAAAAAAAESp5gEAAAAAQinIkYl9Yjmjb6lDzboRzqfFOpw%3DWj6cfL9MKh6OWLgbAIyr1pEjBqMSNqCvDAysUJcn2cQEk55x9J"),
    }

    mcp_config = {
        "command": uv_path,
        "args": ["--directory", str(PROJECT_DIR), "run", "web-search-mcp"],
        "env": env_vars,
        "disabled": False,
        "autoApprove": [],
    }

    print("\nConfiguring 'web-search-mcp' across all AI agent platform settings...")
    for settings_file in MCP_SETTINGS_FILES:
        try:
            settings_file.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            if settings_file.exists():
                try:
                    data = json.loads(settings_file.read_text(encoding="utf-8"))
                except Exception:
                    data = {}

            if "mcpServers" not in data:
                data["mcpServers"] = {}

            data["mcpServers"][SKILL_NAME] = mcp_config
            settings_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            print(f"  ✓ Configured MCP in: {settings_file}")
        except Exception as exc:
            print(f"  ✗ Could not configure MCP in {settings_file}: {exc}")


if __name__ == "__main__":
    install_skills()
    configure_claude_cli()
    configure_all_mcp_servers()
    print("\nAll Skill and MCP configurations completed successfully!")
