
import json
import os
import sys
from urllib.parse import quote

import httpx


def main() -> None:
    base_url = os.environ.get("OTARI_BASE_URL", "").rstrip("/")
    api_key = os.environ.get("OTARI_API_KEY", "")
    server_id = os.environ.get("OTARI_MCP_SERVER_ID", "")

    missing = [
        name
        for name, value in (
            ("OTARI_BASE_URL", base_url),
            ("OTARI_API_KEY", api_key),
            ("OTARI_MCP_SERVER_ID", server_id),
        )
        if not value
    ]

    if missing:
        sys.exit(f"Missing environment variables: {', '.join(missing)}")

    url = (
        f"{base_url}/mcp/servers/"
        f"{quote(server_id, safe='')}/tools"
    )

    try:
        response = httpx.get(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
            timeout=30.0,
            follow_redirects=False,
        )

        print(f"HTTP Status: {response.status_code}")

        response.raise_for_status()
        payload = response.json()

        print("\nDiscovery response:")
        print(json.dumps(payload, indent=2))

        revision = payload.get("server_revision")
        tools = payload.get("tools", [])

        if not revision:
            sys.exit("\nERROR: server_revision missing from response")

        print("\n--- Discovery summary ---")
        print(f"Server ID: {payload.get('server_id')}")
        print(f"Server revision: {revision}")
        print(f"Discovered tools: {len(tools)}")

        for tool in tools:
            print(f"  - {tool.get('name')}")

    except httpx.HTTPStatusError as exc:
        print(f"\nOtari returned HTTP {exc.response.status_code}")
        print(exc.response.text)
        sys.exit(1)

    except httpx.RequestError as exc:
        print(f"\nRequest failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
