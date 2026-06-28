# G Health CLI

`ghealth` is a local-first CLI for user-authorized Google Health API access.

The CLI stores tokens locally and does not include telemetry.

## Installation

You can install `ghealth` directly from this GitHub repository using `uv`:

```bash
uv tool install git+https://github.com/chiragvijay/ghealth-cli.git
```

For local development:

```bash
uv sync
uv run ghealth --help
```

## Setup

Google Health requires bring-your-own Google Cloud OAuth credentials. Create a Google Cloud project, enable the Google Health API, configure an OAuth client, and download the client credentials JSON. See Google's [Health setup guide](https://developers.google.com/health/setup).

```bash
ghealth auth configure --credentials credentials.json
ghealth auth login
ghealth doctor
```

## Usage
```bash
# View daily aggregates (defaults to the last 5 days)
ghealth steps daily --last-days 5
ghealth calories daily --last-days 5
ghealth active-minutes daily --last-days 5
ghealth distance daily --last-days 5

# List specific data points with limit
ghealth sleep list --limit 10
ghealth heart-rate list --limit 20
ghealth weight list --limit 5
ghealth exercise list --limit 5
```

## AI Agent Integration (Using Skills)

For AI agents (like Codex, Cursor, Claude Code, or Gemini), you can install the agent skill to effectively query your Google Health data.

### Installing the Skill

Add this skill directly to your workspace:

```bash
# Install the skill from this repository using skills.sh
npx skills add chiragvijay/ghealth-cli
```

*(Alternatively, you can copy the local [SKILL.md](skills/google-health/SKILL.md) file into your agent's skill directory).*

