"""Semantic Scholar MCP server package."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("semanticscholar-mcp-server")
except PackageNotFoundError:
    __version__ = "0.1.0"
