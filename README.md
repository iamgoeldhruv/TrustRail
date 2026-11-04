# TrustRail

An authorization and transaction-control layer that lets AI agents act
on real systems while keeping every action policy-checked,
human-approved, auditable and recoverable.

## Tech Stack

-   Python 3.12+
-   FastAPI
-   Pydantic
-   Pydantic Settings
-   SQLite (planned)
-   MCP Python SDK
-   HTTPX
-   Pytest
-   Ruff
-   MyPy

## Current Progress

### Project Setup & Scaffolding

-   [x] Initialized Python virtual environment.
-   [x] Created project dependency configuration (`pyproject.toml`).
-   [x] Installed project dependencies.
-   [x] Created backend directory structure.
-   [x] Initialized FastAPI application.
-   [x] Implemented basic `/health` endpoint.
-   [x] Created `Makefile` for common development commands.
-   [x] Created `.env.example` for environment configuration.
-   [x] Created `.gitignore` for excluding secrets and generated files.
-   [x] Added centralized application configuration using Pydantic
    Settings.

### Otari Integration & CLI

- [x] Implemented asynchronous Otari chat-completions client using HTTPX.
- [x] Added custom exception handling for Otari API, authentication, connection and timeout errors.
- [x] Implemented HTTP client lifecycle management.
- [x] Created `trustrail ping` CLI command.
- [x] Verified successful inference through the hosted Otari gateway.
- [x] Implemented asynchronous Otari MCP discovery and execution client using HTTPX.
- [x] Added Pydantic models for MCP discovery and execution responses.
- [x] Added error handling for MCP discovery and execution failures.
- [x] Created scripts to verify MCP discovery and tool execution through the actual Otari API.
- [x] Verified successful read-only `get_status` execution through Otari using a workspace API key.

### MCP Server Spike

- [x] Implemented a Python MCP server using Streamable HTTP.
- [x] Added `get_status` (read) and `update_status` (write) tools.
- [x] Verified tool discovery and execution using MCP Inspector.
- [x] Deployed the MCP server publicly over HTTPS on Railway.
- [x] Registered the MCP server in Otari with an explicit tool allowlist.
- [x] Integrated Otari MCP tool discovery using `GET /api/v1/mcp/servers/{server_id}/tools`.
- [x] Verified discovery of allowlisted tools and captured the returned `server_revision`.


## Running Locally

``` bash
source .venv/bin/activate
make run
```

## Directory Structure

``` text
TrustRail/
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   └── commands/
│   │       ├── __init__.py
│   │       └── ping.py
│   ├── otari/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── exceptions.py
│   │   └── mcp.py
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
├── mcp_spike/
│   ├── __init__.py
│   └── server.py
│
├── tests/
│   └── otari/
│       └── test_mcp.py
│
├── scripts/
│   ├── discover_otari_mcp.py
│   └── execute_otari_mcp.py
│
├── docs/
├── Dockerfile
├── requirements.txt
├── pyproject.toml
├── Makefile
├── .env.example
├── .gitignore
└── README.md