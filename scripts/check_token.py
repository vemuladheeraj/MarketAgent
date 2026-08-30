"""INDstocks access-token health check.

Verifies whether the token currently in .env is accepted by the INDstocks API
without ever printing the token itself. Run before starting the live agent:

    .venv\\Scripts\\python.exe scripts/check_token.py

Exit codes: 0 = token valid, 1 = token rejected/missing.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# Windows consoles default to cp1252; force UTF-8 so ✓/✗ render safely.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx  # noqa: E402

BASE_URL = "https://api.indstocks.com"

#: Cheap endpoints that require auth — mirrors what run_live.ps1 hits first.
CHECKS: list[tuple[str, dict[str, str]]] = [
    ("GET /market/instruments?source=index", {"source": "index"}),
    ("GET /market/quotes/full (NIFTY)", {}),
]


def load_token() -> str:
    """Read INDSTOCKS_ACCESS_TOKEN from the environment, falling back to .env."""
    try:  # honour the app's own env loading when available
        from app.config.settings import load_env_file  # type: ignore[attr-defined]

        load_env_file()
    except Exception:
        pass
    token = os.getenv("INDSTOCKS_ACCESS_TOKEN", "").strip()
    if token:
        return token

    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("INDSTOCKS_ACCESS_TOKEN="):
                token = stripped.split("=", 1)[1].strip().strip('"').strip("'")
                break
    return token


def main() -> int:
    token = load_token()
    if not token:
        print("FAIL: INDSTOCKS_ACCESS_TOKEN is not set in .env or the environment.")
        print("      Generate one at https://indstocks.com/app/api-trading/access-tokens")
        return 1

    print(f"Token loaded ({len(token)} chars, not printed). Probing {BASE_URL} ...")
    rejected = False
    with httpx.Client(timeout=10.0, headers={"Authorization": token}) as client:
        for label, params in CHECKS:
            try:
                resp = client.get(f"{BASE_URL}/market/instruments" if "instruments" in label else f"{BASE_URL}/market/quotes/full", params=params)
            except httpx.HTTPError as exc:
                print(f"  ?   {label}: network error ({exc})")
                continue
            if resp.status_code in (401, 403):
                rejected = True
                print(f"  [FAIL] {label}: HTTP {resp.status_code} -- token rejected")
            elif resp.status_code == 200:
                print(f"  [OK]   {label}: HTTP 200")
            else:
                print(f"  [WARN] {label}: HTTP {resp.status_code} (unexpected, not an auth issue)")

    if rejected:
        print()
        print("VERDICT: token is EXPIRED/INVALID. The API will 403 every call.")
        print("  1. Open https://www.indstocks.com/app/api-trading/access-tokens")
        print("  2. Generate a fresh 24-hour token")
        print("  3. Update INDSTOCKS_ACCESS_TOKEN in .env")
        print("  4. Re-run this check, then start .\\scripts\\run_live.ps1")
        return 1

    print()
    print("VERDICT: token is VALID — safe to start run_live.ps1.")
    print("  (Tokens expire every 24h; re-run this check any time.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
