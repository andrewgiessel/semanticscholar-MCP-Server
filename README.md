# 🎓 Semantic Scholar MCP Server

[![smithery badge](https://smithery.ai/badge/@JackKuo666/semanticscholar-mcp-server)](https://smithery.ai/server/@JackKuo666/semanticscholar-mcp-server)

This project implements a Model Context Protocol (MCP) server for interacting with the Semantic Scholar API. It provides tools for searching papers, retrieving paper and author details, and fetching citations and references.

## ✨ Features

- 🔍 Search for papers on Semantic Scholar
- 📄 Retrieve detailed information about specific papers
- 👤 Get author details
- 🔗 Fetch citations and references for a paper

## 📋 Prerequisites

- 🐍 Python 3.10+
- ⚡ `uv`

## 🚀 Installation

### Installing via Smithery

To install semanticscholar Server for Claude Desktop automatically via [Smithery](https://smithery.ai/server/@JackKuo666/semanticscholar-mcp-server):

#### claude

```sh
npx -y @smithery/cli@latest install @JackKuo666/semanticscholar-mcp-server --client claude --config "{}"
```

#### Cursor

Paste the following into Settings → Cursor Settings → MCP → Add new server:

- Mac/Linux

```sh
npx -y @smithery/cli@latest run @JackKuo666/semanticscholar-mcp-server --client cursor --config "{}" 
```

#### Windsurf

```sh
npx -y @smithery/cli@latest install @JackKuo666/semanticscholar-mcp-server --client windsurf --config "{}"
```

### CLine

```sh
npx -y @smithery/cli@latest install @JackKuo666/semanticscholar-mcp-server --client cline --config "{}"
```

1. Clone this repository:

   ```sh
   git clone https://github.com/JackKuo666/semanticscholar-MCP-Server.git
   cd semanticscholar-MCP-Server
   ```

2. Sync the project dependencies:

   ```sh
   uv sync
   ```

## 🖥️ Usage

1. Start the Semantic Scholar MCP server:

   ```sh
   uv run python semantic_scholar_server.py
   ```

2. The server will start and listen for MCP requests.

3. Use an MCP client to interact with the server and access the following tools:

   - 🔍 `search_semantic_scholar`: Search for papers using a query string
   - 📄 `get_semantic_scholar_paper_details`: Get details of a specific paper
   - 👤 `get_semantic_scholar_author_details`: Get details of a specific author
   - 🔗 `get_semantic_scholar_citations_and_references`: Get citations and references for a paper

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
        "semantic_scholar_server.py"
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
        "semantic_scholar_server.py"
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
        "semantic_scholar_server.py"
      ],
      "env": {},
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

## 📁 File Structure

- 📜 `semantic_scholar_search.py`: Contains functions for interacting with the Semantic Scholar API
- 🖥️ `semantic_scholar_server.py`: Implements the MCP server and defines the available tools

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
