# Contributing to Thinking Graph

Thanks for your interest in contributing to **Thinking Graph**.

This project is currently in an **early stage (alpha/beta)**. Contributions are welcome, especially for:
- bug fixes
- documentation improvements
- tests
- code cleanup / refactoring
- usability improvements
- small, focused feature additions

## Before You Start

Please read the README first and make sure you can run the project locally.

For larger changes (new features, major refactors, architecture changes), please open an issue first to discuss the proposal before submitting a PR.

## Ways to Contribute

You can contribute in several ways:

- **Report bugs** (repro steps, logs, screenshots, environment info)
- **Suggest features** (use case, expected behavior, alternatives considered)
- **Improve documentation** (README, setup, troubleshooting, examples)
- **Write tests** (unit/integration tests for core modules)
- **Submit code fixes** (small, scoped, reviewable PRs)

## Development Setup

> The project currently uses Python 3.11+.

### 1) Clone the repository

```bash
git clone https://github.com/LunaticLegacy/thinking_graph.git
cd thinking_graph
````

### 2) Create and activate a virtual environment

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

### 3) Install dependencies

```bash
pip install -r requirements.txt
```

### 4) Create local config

Copy the example configuration file and edit it for your local environment:

```bash
cp app_config_example.toml app_config.toml
```

(Windows PowerShell)

```powershell
Copy-Item app_config_example.toml app_config.toml
```

### 5) Run the app

```bash
python main.py
```

If you are contributing to the frontend/UI, also verify that the relevant pages render correctly in the browser.

## Development Guidelines

### Keep changes focused

Please avoid mixing unrelated changes in one PR. Small PRs are easier to review and merge.

### Prefer discussion for major changes

Open an issue before implementing:

* new architecture modules
* major dependency changes
* API contract changes
* persistent storage/schema changes

### Backward compatibility

If your change may affect existing config/data behavior, document it clearly in the PR description.

## Coding Standards

* Follow **PEP 8** style for Python code.
* Use clear names and keep functions/classes focused.
* Add type hints where practical.
* Avoid introducing hidden global state.
* Prefer explicit error handling with useful messages/logs.

If linting/formatting tools are configured (e.g., `ruff`, `black`), please run them before submitting a PR.

## Testing

Tests are still being expanded (`tests/` is a work in progress), but contributions should not break core behavior.

### What to test (high priority)

* repository/data access behavior
* graph CRUD operations
* app startup / app factory creation
* LLM service error handling (timeouts, malformed responses)

### Run tests

If `pytest` is configured:

```bash
pytest
```

If you add new functionality, please include tests whenever possible.

## Commit Message Guidelines

Use clear commit messages. Conventional Commits are recommended (not required), for example:

* `feat: add graph node validation`
* `fix: prevent silent db fallback in production`
* `docs: update README setup instructions`
* `test: add repository transaction rollback tests`

## Pull Request Guidelines

When submitting a PR, please include:

* **What changed**
* **Why it changed**
* **How to test it**
* **Any breaking changes** (if applicable)
* screenshots/GIFs for UI changes (if applicable)

### PR Checklist

* [ ] My changes are focused and related to a single topic
* [ ] I tested the change locally
* [ ] I updated documentation (if needed)
* [ ] I added or updated tests (if applicable)
* [ ] I did not commit secrets, API keys, or local config files

## Issue Reporting Guidelines

### Bug reports

Please include:

* operating system
* Python version
* steps to reproduce
* expected behavior
* actual behavior
* logs / error messages
* screenshots (if UI-related)

### Feature requests

Please include:

* problem/use case
* proposed solution
* alternative approaches (optional)

## Security Issues

If you discover a security vulnerability, please **do not** open a public issue.

Instead, contact the maintainer privately (add your preferred contact method here, e.g. email).

Example:

* Email: `your-email@example.com`

## Code of Conduct

Please be respectful and constructive in discussions and reviews.

(You can add a separate `CODE_OF_CONDUCT.md` later if needed.)

## License

By contributing, you agree that your contributions will be licensed under the same license as this project.
