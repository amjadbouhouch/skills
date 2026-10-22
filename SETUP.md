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

### rea

Reverse engineers apps, games and websites: gives the agent tools to inspect the code behind them. Its setup command registers the MCP server and installs a workflow skill. Source: https://github.com/morluto/rea

Requires Node.js 22.19+ (or 24.11+, or 26+) and npm. Native binary analysis also needs Hopper, Ghidra or IDA. Leave that out unless the user asks for it.

Preview the plan, show it to the user, then apply it:

```bash
npx -y rea-agents@latest setup --client claude_code --dry-run
npx -y rea-agents@latest setup --client claude_code --yes
```

For another agent, swap the `--client` id (for example `codex` or `cursor`), or use `--all-detected` to configure every supported agent setup finds. Restart the agent afterwards.

Check: `npx -y rea-agents@latest doctor --client claude_code --skill --json` reports ready, and `claude mcp get rea` shows the server connected.

## Skills

### fleet

Coordinates agent sessions across machines through a shared synced folder. Source: [`skills/fleet`](skills/fleet)

Requires Node.js (for `npx`).

```bash
npx skills add amjadbouhouch/skills --skill fleet -g -y
```

Check: `~/.agents/skills/fleet/SKILL.md` exists.

### product-lifecycle

The lifecycle a fleet orchestrator runs work through: planner, plan approval, Notion task, build, `/code-review`, local merge. Source: [`skills/product-lifecycle`](skills/product-lifecycle)

Requires Node.js (for `npx`), the Notion CLI below, and the `code-review` skill, installed with it:

```bash
npx skills add amjadbouhouch/skills --skill product-lifecycle -g -y
npx skills add https://github.com/mattpocock/skills --skill code-review -g -y
```

Check: `~/.agents/skills/product-lifecycle/SKILL.md` and `~/.agents/skills/code-review/SKILL.md` exist.

### grill-with-docs

Stress-tests a plan against the project's domain model, sharpens terminology, and updates CONTEXT.md and ADRs as decisions settle. It calls the `grilling` and `domain-modeling` skills, so install those with it. Source: https://github.com/mattpocock/skills

Requires Node.js (for `npx`).

```bash
npx skills add https://github.com/mattpocock/skills --skill grill-with-docs --skill grilling --skill domain-modeling -g -y
```

Check: `~/.agents/skills/grill-with-docs/SKILL.md`, `~/.agents/skills/grilling/SKILL.md` and `~/.agents/skills/domain-modeling/SKILL.md` exist.

### wizard

Writes a bash script that walks a human step by step through a tedious manual procedure, such as configuring third-party services or writing `.env` values and GitHub secrets. Source: https://github.com/mattpocock/skills

Requires Node.js (for `npx`).

```bash
npx skills add https://github.com/mattpocock/skills --skill wizard -g -y
```

Check: `~/.agents/skills/wizard/SKILL.md` exists.

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

### agent-pm (`apm`)

A command-line project manager for agents: projects, milestones, tasks and subtasks, statuses, links, claims, history. One binary with SQLite built in; every command takes `--json`. Source: https://github.com/amjadbouhouch/agent-pm

macOS and Linux (x64, arm64):

```bash
curl -fsSL https://raw.githubusercontent.com/amjadbouhouch/agent-pm/main/install.sh | sh -s -- --no-modify-path
```

This puts `apm` in `~/.agent-pm/bin`. Add that directory to `PATH` in the user's shell profile. Re-run to upgrade.

Windows (x64, PowerShell 5.1 or 7):

```powershell
irm https://raw.githubusercontent.com/amjadbouhouch/agent-pm/main/install.ps1 | iex
```

This puts `apm.exe` in `%USERPROFILE%\.agent-pm\bin` and offers to add it to the user `PATH`.

On musl/Alpine, or with Rust installed: `cargo install --git https://github.com/amjadbouhouch/agent-pm`.

Data lives in `~/.agent-pm/apm.db` (override with `--db PATH` or `$APM_DB`). Agents set `APM_AGENT` to their name; `apm guide` prints the workflow and JSON contract.

Check: `apm db` prints the database path and schema version.

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
