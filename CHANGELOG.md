# Changelog

## Unreleased

### Added
- Package-based server entrypoint with `uv` workflows.
- Semantic Scholar paper search, paper details, author details, author search, author papers, recommendations, and citations/reference MCP tools.
- Public-API resilience with client-side throttling, `tenacity` retries, and automatic fallback when a configured API key gets `403`.
- Diagnostic command for validating Semantic Scholar API behavior.
- Unit tests for helper and server layers.
- Ruff, pyright, pre-commit, and GitHub Actions CI configuration.

### Changed
- Documentation rewritten for the maintained fork and public-package workflow.
