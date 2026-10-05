# Daily tools setup

Instructions for an AI agent setting up a new machine. Install every entry below at user (global) scope, skip entries that are already installed, then run each entry's check.

The commands target Claude Code. For another agent, add the JSON under `mcpServers` in that agent's global MCP config.

## MCP servers

### deepwiki

Answers questions about any public GitHub repository from its generated wiki. Source: https://github.com/mcp/cognitionai/deepwiki

```bash
claude mcp add --scope user --transport http deepwiki https://mcp.deepwiki.com/mcp
```

```json
{
  "mcpServers": {
    "deepwiki": {
      "type": "http",
      "url": "https://mcp.deepwiki.com/mcp"
    }
  }
}
```

Check: `claude mcp get deepwiki` shows the server connected.

### android-mcp

Drives an Android device or emulator. Source: https://github.com/CursorTouch/Android-MCP

Requires:

- `uv` (`brew install uv`, or `curl -LsSf https://astral.sh/uv/install.sh | sh`). `uvx` fetches Python 3.13 itself.
- `adb` on `PATH` (Android SDK platform-tools, or `brew install android-platform-tools`), and a device or emulator with USB debugging on.

```bash
claude mcp add-json --scope user android-mcp '{"command":"uvx","args":["--python","3.13","android-mcp"]}'
```

```json
{
  "mcpServers": {
    "android-mcp": {
      "command": "uvx",
      "args": ["--python", "3.13", "android-mcp"]
    }
  }
}
```

Check: `claude mcp get android-mcp` shows the server connected, and `adb devices` lists a device.

## Skills

### fleet

Coordinates agent sessions across machines through a shared synced folder. Source: [`skills/fleet`](skills/fleet)

Requires Node.js (for `npx`).

```bash
npx skills add amjadbouhouch/skills --skill fleet -g -y
```

Check: `~/.agents/skills/fleet/SKILL.md` exists.

## CLIs

### Notion CLI (`ntn`)

Notion access goes through this CLI only. Don't install a Notion MCP server or Notion skill.

macOS and Linux:

```bash
curl -fsSL https://ntn.dev | bash
```

Windows (requires Node.js):

```bash
npm install -g ntn
```

Then ask the user to run `ntn login`, which opens a browser to sign in. On a machine without a browser, use `ntn login --no-browser`.

Check: `ntn doctor` passes and `ntn whoami` prints the user.

## Browser

Install one browser tool, chosen by OS.

### macOS: ego-lite

A Chromium browser that agents drive through the `ego-browser` skill, using the user's logged-in sessions. Docs: https://lite.ego.app/document/en/docs/claude-code

The install is a GUI step, so hand it to the user:

1. Run `open "https://lite.ego.app/download?auto=1"` to download the DMG.
2. Ask the user to open the DMG, double-click the ego (lite) icon to install, then open ego (lite) and finish onboarding. Onboarding installs the `ego-browser` skill.
3. Restart any running Claude Code session so the skill list refreshes.

Check: `/Applications/ego lite.app` exists and `~/.claude/skills/ego-browser` exists.

### Windows and Linux: agent-browser

Browser automation CLI for agents. Source: https://github.com/vercel-labs/agent-browser

Requires Node.js (for `npx`).

```bash
npx skills add https://github.com/vercel-labs/agent-browser --skill agent-browser -g -y
```

Check: `~/.agents/skills/agent-browser/SKILL.md` exists.
