# Changelog

## Unreleased

### Added
- Package-based server entrypoint with `uv` workflows.
- Semantic Scholar paper search, paper details, author details, author search, author papers, recommendations, and citations/reference MCP tools.
- Public-API resilience with client-side throttling, `tenacity` retries, and automatic fallback when a configured API key gets `403`.
- Diagnostic command for validating Semantic Scholar API behavior.
- Unit tests for helper and server layers.
- Ruff, pyright, pre-commit, and GitHub Actions CI configuration.
- Advanced filtered paper search, bulk paper search, multi-paper recommendations, title matching, autocomplete, BibTeX export, snippet search, author batch lookup, and status/health MCP tools with docs and validation tests.

### Changed
- Documentation rewritten for the maintained fork and public-package workflow.
