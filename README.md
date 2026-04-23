# 🎓 Semantic Scholar MCP Server

This project implements a Model Context Protocol (MCP) server for interacting with the Semantic Scholar API. It provides tools for searching papers, retrieving paper and author details, and fetching citations and references.

## Why This Fork?

This repository is a maintained fork of the original project at [JackKuo666/semanticscholar-MCP-Server](https://github.com/JackKuo666/semanticscholar-MCP-Server).
The goal of this fork is to keep the original idea while improving packaging, reliability, typing, and developer tooling.

## ✨ Features

- 🔍 Search for papers on Semantic Scholar
- 📄 Retrieve detailed information about specific papers
- 🗂️ Fetch multiple papers in a batch
- 👤 Get author details
- 👥 Search for authors and list their papers
- 💡 Get recommended papers for a seed paper
- 🔗 Fetch paginated citations and references with rich metadata

## 📋 Prerequisites

- 🐍 Python 3.10+
- ⚡ `uv`

## 🚀 Installation

1. Clone this repository:

   ```sh
   git clone <your-fork-url>
   cd semanticscholar-MCP-Server
   ```

2. Sync the project dependencies:

   ```sh
   uv sync
   ```

3. Optional: add a Semantic Scholar API key to a local `.env` file:

   ```sh
   echo "SEMANTIC_SCHOLAR_API_KEY=your-key-here" > .env
   ```

4. Optional: install the git hooks:

   ```sh
   uv run pre-commit install
   ```

## 🖥️ Usage

1. Start the Semantic Scholar MCP server:

   ```sh
   uv run semanticscholar-mcp-server
   ```

2. The server will start and listen for MCP requests.

3. Use an MCP client to interact with the server and access the following tools:

   - 🔍 `search_semantic_scholar`: Search for papers using a query string
   - 📄 `get_semantic_scholar_paper_details`: Get details of a specific paper
   - 🗂️ `get_semantic_scholar_papers_batch`: Get details for multiple papers in one request
   - 👤 `get_semantic_scholar_author_details`: Get details of a specific author
   - 👥 `search_semantic_scholar_authors`: Search for authors by name
   - 📚 `get_semantic_scholar_author_papers`: Get papers for a specific author
   - 💡 `get_semantic_scholar_recommendations`: Get recommended papers for a seed paper
   - 🔗 `get_semantic_scholar_citations`: Get a paginated page of citations for a paper
   - 🔗 `get_semantic_scholar_references`: Get a paginated page of references for a paper
   - 🔗 `get_semantic_scholar_citations_and_references`: Get bounded pages of both citations and references for a paper

This repository uses the `semanticscholar_mcp_server` Python package as its only entrypoint.
If `SEMANTIC_SCHOLAR_API_KEY` is configured, the server will try authenticated requests first. If Semantic Scholar responds with `403 Forbidden`, the server automatically disables key usage for the rest of the process and falls back to the public API. All Semantic Scholar requests are client-side throttled to at most 1 request per second, and public API requests also use tenacity-based exponential backoff retries for transient `429` rate limits.

Large citation and reference sets are exposed through paginated tools so large papers stay usable in MCP clients. Related-paper responses include richer fields such as abstract, venue, citation count, publication types, URLs, and external ids when available.

### Notes on Citation Harvesting

The paginated citation tools were verified on the `Large Language Bayes` seed paper. `get_semantic_scholar_citations` paginated cleanly and returned the fields needed for triage and CSV export workflows, including `paperId`, `title`, `abstract`, `year`, `authors`, `venue`, `citationCount`, `externalIds` / DOI / arXiv ids, `contexts`, and `isInfluential`. In practice, this removes both of the earlier blockers: response size is no longer the limiting factor, and the returned metadata is rich enough to build a filtered shortlist without a second round trip per citing paper.

One caveat to keep an eye on: on that small seed, the response came back with `total: null` and `hasMore: true` at the same time. That pagination behavior should be verified again on a medium-sized seed before depending on `total` for a long-running harvest loop.

### Behavior Knobs

The following environment variables can be used to tune runtime behavior:

- `SEMANTIC_SCHOLAR_API_KEY`: optional Semantic Scholar API key
- `SEMANTIC_SCHOLAR_MIN_SECONDS_BETWEEN_REQUESTS`: request spacing, defaults to `1.0`
- `SEMANTIC_SCHOLAR_RETRY_ATTEMPTS`: retry attempts for `429` responses, defaults to `6`
- `SEMANTIC_SCHOLAR_RETRY_MIN_WAIT_SECONDS`: minimum exponential backoff wait, defaults to `1.0`
- `SEMANTIC_SCHOLAR_RETRY_MAX_WAIT_SECONDS`: maximum exponential backoff wait, defaults to `30.0`
- `SEMANTIC_SCHOLAR_LOG_LEVEL`: logging level, defaults to `INFO`

## Development

Run the full local quality suite with:

```sh
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

If you want automatic formatting and lint fixes:

```sh
uv run ruff check --fix .
uv run ruff format .
uv run pre-commit run --all-files
```

## Docker

Build the image with:

```sh
docker build -t semanticscholar-mcp-server .
```

Run the packaged server with:

```sh
docker run --rm -i \
  -e SEMANTIC_SCHOLAR_API_KEY="$SEMANTIC_SCHOLAR_API_KEY" \
  semanticscholar-mcp-server
```

## Usage with Claude Desktop

Add this configuration to your `claude_desktop_config.json`:

(Mac OS)

```json
{
  "mcpServers": {
    "semanticscholar": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/semanticscholar-MCP-Server",
        "run",
        "python",
        "-m",
        "semanticscholar_mcp_server"
      ]
      }
  }
}
```

(Windows version):

```json
{
  "mcpServers": {
    "semanticscholar": {
      "command": "uv",
      "args": [
        "--directory",
        "D:\\code\\YOUR\\PATH\\semanticscholar-MCP-Server",
        "run",
        "python",
        "-m",
        "semanticscholar_mcp_server"
      ],
      "env": {},
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

Using with Cline

```json
{
  "mcpServers": {
    "semanticscholar": {
      "command": "uv",
      "args": [
        "--directory",
        "/home/YOUR/PATH/semanticscholar-MCP-Server",
        "run",
        "python",
        "-m",
        "semanticscholar_mcp_server"
      ],
      "env": {},
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

## 📁 File Structure

- 📦 `semanticscholar_mcp_server/`: Package containing the MCP server, entrypoint, and Semantic Scholar client helpers
- 🧪 `tests/`: `pytest` unit tests for the helper layer
- 🔄 `.github/workflows/ci.yml`: CI for linting, formatting, type checking, and tests
- 📝 `CHANGELOG.md`: Fork-specific change history

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
