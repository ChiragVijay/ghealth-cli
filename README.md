# G Health CLI

`ghealth` is a local-first CLI for user-authorized Google Health API access.

The CLI stores tokens locally and does not include telemetry.

## Prerequisites

1. **Install `uv`** (Python package manager):

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

   See the [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/) for other methods.

2. **Set up a Google Cloud project with the Health API**:

   Follow Google's official [Health API setup guide](https://developers.google.com/health/setup) to:
   - Create a Google Cloud project
   - Enable the Google Health API
   - Configure an OAuth 2.0 consent screen
   - Create an OAuth client ID (Desktop application type)
   - Download the client credentials JSON file

## Installation

You can install `ghealth` directly from this GitHub repository using `uv`:

```bash
uv tool install https://github.com/chiragvijay/ghealth-cli.git
```

For local development:

```bash
uv sync
uv run ghealth --help
```

## Setup

Point the CLI at your downloaded OAuth credentials and log in:

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

Add this skill directly to your workspace using skills.sh:

```bash
npx skills add chiragvijay/ghealth-cli
```

*(Alternatively, you can copy the local [SKILL.md](skills/google-health/SKILL.md) file into your agent's skill directory).*
