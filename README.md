# 🎓 Semantic Scholar MCP Server

This project implements a Model Context Protocol (MCP) server for interacting with the Semantic Scholar API. It provides tools for searching papers, retrieving paper and author details, and fetching citations and references.

## ✨ Features

- 🔍 Search for papers on Semantic Scholar
- 📄 Retrieve detailed information about specific papers
- 👤 Get author details
- 👥 Search for authors and list their papers
- 💡 Get recommended papers for a seed paper
- 🔗 Fetch citations and references for a paper

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

## 🖥️ Usage

1. Start the Semantic Scholar MCP server:

   ```sh
   uv run semanticscholar-mcp-server
   ```

2. The server will start and listen for MCP requests.

3. Use an MCP client to interact with the server and access the following tools:

   - 🔍 `search_semantic_scholar`: Search for papers using a query string
   - 📄 `get_semantic_scholar_paper_details`: Get details of a specific paper
   - 👤 `get_semantic_scholar_author_details`: Get details of a specific author
   - 👥 `search_semantic_scholar_authors`: Search for authors by name
   - 📚 `get_semantic_scholar_author_papers`: Get papers for a specific author
   - 💡 `get_semantic_scholar_recommendations`: Get recommended papers for a seed paper
   - 🔗 `get_semantic_scholar_citations_and_references`: Get citations and references for a paper

This repository uses the `semanticscholar_mcp_server` Python package as its only entrypoint.
If `SEMANTIC_SCHOLAR_API_KEY` is configured, the server will try authenticated requests first. If Semantic Scholar responds with `403 Forbidden`, the server automatically disables key usage for the rest of the process and falls back to the public API. All Semantic Scholar requests are client-side throttled to at most 1 request per second, and public API requests also use tenacity-based exponential backoff retries for transient `429` rate limits.

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

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
