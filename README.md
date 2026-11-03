# TrustRail

An authorization and transaction-control layer that lets AI agents act on real systems while keeping every action policy-checked, human-approved, auditable and recoverable.

## Tech Stack

- Python 3.12+
- FastAPI
- Pydantic
- Pydantic Settings
- SQLite (planned)
- Pytest
- Ruff
- MyPy

## Current Progress

### Project Setup & Scaffolding

- [x] Initialized Python virtual environment.
- [x] Created project dependency configuration (`pyproject.toml`).
- [x] Installed project dependencies.
- [x] Created backend directory structure.
- [x] Initialized FastAPI application.
- [x] Implemented basic `/health` endpoint.
- [x] Created `Makefile` for common development commands.
- [x] Created `.env.example` for environment configuration.
- [x] Created `.gitignore` for excluding secrets and generated files.
- [x] Added centralized application configuration using Pydantic Settings.
### Otari Integration & CLI

- [x] Implemented asynchronous Otari chat-completions client using HTTPX.
- [x] Added custom exception handling for Otari API, authentication, connection and timeout errors.
- [x] Implemented HTTP client lifecycle management.
- [x] Created `trustrail ping` CLI command.
- [x] Verified successful inference through the hosted Otari gateway.

## Running Locally

```bash
source .venv/bin/activate
make run

## Directory Structure
TrustRail/
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py
│   │
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   └── commands/
│   │       ├── __init__.py
│   │       └── ping.py
│   ├── otari/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   └── exceptions.py
│   │
│   ├── policy/
│   ├── authz/
│   ├── facts/
│   ├── txn/
│   ├── approvals/
│   ├── ledger/
│   ├── agent/
│   ├── reconcile/
│   ├── scenarios/
│   └── fakeotari/
│
├── mcp_github/
├── tests/
│   └── otari/
├── scripts/
├── docs/
│
├── pyproject.toml
├── Makefile
├── .env.example
├── .gitignore
└── README.md