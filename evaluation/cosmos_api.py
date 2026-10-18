"""Minimal authenticated client for the loopback-published COSMOS JSON-RPC API."""

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]


class CosmosApiError(RuntimeError):
    pass


def lab_setting(name, root=ROOT):
    """Read a public lab setting from the environment or the Compose .env file."""
    if value := os.environ.get(name):
        return value
    try:
        lines = (Path(root) / ".env").read_text().splitlines()
    except OSError as exc:
        raise CosmosApiError(f"Cannot read {name}: {exc}") from exc
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == name:
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            return value
    raise CosmosApiError(f"{name} is not set in the environment or {Path(root) / '.env'}")


def loopback_url(setting, root=ROOT):
    """Build a loopback URL from one validated lab port setting."""
    try:
        port = int(lab_setting(setting, root))
        if not 1 <= port <= 65535:
            raise ValueError("invalid host port")
    except (TypeError, ValueError) as exc:
        raise CosmosApiError(f"{setting} must be a valid TCP port: {exc}") from exc
    return f"http://127.0.0.1:{port}"


class CosmosApi:
    """Call the same authenticated HTTP endpoint used by external COSMOS clients."""

    def __init__(self, base_url, password, timeout=5):
        self.base_url = base_url.rstrip("/")
        self.password = password
        self.timeout = timeout
        self.request_id = 0
        self.session_token = None

    @classmethod
    def from_environment(cls, root=ROOT):
        base_url = os.environ.get("LAB_URL") or loopback_url("LAB_UI_PORT", root)
        return cls(base_url, lab_setting("LAB_API_PASSWORD", root))

    def authenticate(self):
        """Exchange the frontend password for a COSMOS session token once."""
        if self.session_token:
            return self.session_token
        request = Request(
            self.base_url + "/openc3-api/auth/verify",
            data=json.dumps({"password": self.password}).encode(),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "spacecop-x86-evaluation",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                token = response.read().decode().strip()
        except HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise CosmosApiError(f"COSMOS authentication HTTP {exc.code}: {detail}") from exc
        except (OSError, URLError, ValueError) as exc:
            raise CosmosApiError(f"COSMOS authentication failed: {exc}") from exc
        if not token:
            raise CosmosApiError("COSMOS authentication returned no session token")
        self.session_token = token
        return token

    def call(self, method, *params, **keyword_params):
        session_token = self.authenticate()
        self.request_id += 1
        keyword_params.setdefault("scope", "DEFAULT")
        body = json.dumps({
            "jsonrpc": "2.0",
            "method": method,
            "params": list(params),
            "keyword_params": keyword_params,
            "id": self.request_id,
        }).encode()
        request = Request(
            self.base_url + "/openc3-api/api",
            data=body,
            headers={
                "Authorization": session_token,
                "Content-Type": "application/json-rpc",
                "User-Agent": "spacecop-x86-evaluation",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.load(response)
        except HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            try:
                error = json.loads(detail).get("error")
                message = error.get("message") if isinstance(error, dict) else None
            except (json.JSONDecodeError, AttributeError):
                message = None
            if message:
                raise CosmosApiError(
                    f"COSMOS API {method} failed (HTTP {exc.code}): {message}"
                ) from exc
            raise CosmosApiError(f"COSMOS API HTTP {exc.code}: {detail[:300]}") from exc
        except (OSError, URLError, ValueError) as exc:
            raise CosmosApiError(f"COSMOS API request failed: {exc}") from exc
        if result.get("id") != self.request_id:
            raise CosmosApiError(f"COSMOS API returned mismatched response id: {result.get('id')}")
        if error := result.get("error"):
            message = error.get("message", str(error)) if isinstance(error, dict) else str(error)
            raise CosmosApiError(f"COSMOS API {method} failed: {message}")
        if "result" not in result:
            raise CosmosApiError(f"COSMOS API {method} returned no result")
        return result["result"]
