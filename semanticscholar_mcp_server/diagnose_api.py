import hashlib
import os
from typing import Any

import requests

from semanticscholar_mcp_server.search import PROJECT_ROOT, initialize_client


API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"


def _mask_key(key: str | None) -> str:
    if not key:
        return "missing"
    fingerprint = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    return f"present len={len(key)} sha256={fingerprint}"


def _summarize_response(response: requests.Response) -> dict[str, Any]:
    body = response.text.replace("\n", " ")[:300]
    return {
        "status_code": response.status_code,
        "body_preview": body,
    }


def main() -> None:
    key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")

    print(f"project_root={PROJECT_ROOT}")
    print(f"env_file_exists={(PROJECT_ROOT / '.env').exists()}")
    print(f"api_key={_mask_key(key)}")

    client = initialize_client()
    print(f"client_type={type(client).__name__}")

    params = {
        "query": "transformer models",
        "limit": 1,
        "fields": "title",
    }

    anonymous_response = requests.get(API_URL, params=params, timeout=30)
    print(f"anonymous={_summarize_response(anonymous_response)}")

    if not key:
        print("authenticated=skipped no API key loaded")
        return

    authenticated_response = requests.get(
        API_URL,
        params=params,
        headers={"x-api-key": key},
        timeout=30,
    )
    print(f"authenticated={_summarize_response(authenticated_response)}")


if __name__ == "__main__":
    main()
