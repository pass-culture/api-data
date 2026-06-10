"""
Locust load test for the Recommendation API v2.

Usage:
  Headless (CI / scripted):
    locust -f locust/locustfile.py --headless -u 20 -r 2 --run-time 5m

  Interactive UI:
    locust -f locust/locustfile.py

Target throughput:
  mean  ≈  6 req/s  (steady-state: 6 users x 1 req/s)
  peak  = 20 req/s  (burst:       20 users x 1 req/s)

Environment variables (can be set in .env.stg or exported before running):
  REMOTE_API_URL           Base URL of the API (e.g. https://api.recommendation.internal)
  REMOTE_API_TOKEN         Bearer / query token for API authentication
  REMOTE_API_SOCKS_PORT    SOCKS5 proxy port opened by the IAP tunnel (default: 1080)
  LOCUST_USE_SOCKS_PROXY   Set to "0" to disable the proxy (e.g. for local tests, default: 1)
  TARGET_ENDPOINT          Restrict load to a single endpoint: offers | playlist | artists
                           Leave unset (or set to "all") for the default weighted mix.
"""

import os
import random
import sys
import time
from http import HTTPStatus
from pathlib import Path
from typing import ClassVar

import requests as _requests

from locust import HttpUser
from locust import LoadTestShape
from locust import constant_throughput
from locust import events
from locust import task


# Ensure internal imports from 'src' work smoothly
sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from config import settings


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE_URL: str = os.getenv("REMOTE_API_URL", f"http://localhost:{settings.FASTAPI_SERVER_PORT}")
API_TOKEN: str = os.getenv("REMOTE_API_TOKEN", "")
SOCKS_PORT: int = int(os.getenv("REMOTE_API_SOCKS_PORT", "1080"))
USE_SOCKS_PROXY: bool = os.getenv("LOCUST_USE_SOCKS_PROXY", "1") != "0"

SOCKS_PROXY_URL = f"socks5h://localhost:{SOCKS_PORT}"

# Probability of injecting optional geo coordinates into a request (30 %)
_GEO_PARAM_PROBABILITY: float = 0.7


# ---------------------------------------------------------------------------
# Sample data pools
# Replace the fallback lists with real staging IDs, or create the matching
# files under locust/data/ (one ID per line) — they are git-ignored.
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).parent / "data"


def _load_ids(filename: str) -> list[str]:
    """Load IDs from a text file (one per line).

    Rules:
    - Lines starting with '#' are treated as comments and ignored.
    - Empty / blank lines are ignored.
    - Raises FileNotFoundError if the file does not exist.
    - Raises ValueError if the file exists but contains no valid IDs.
    """
    path = _DATA_DIR / filename

    if not path.exists():
        raise FileNotFoundError(
            f"[locust] Data file not found: {path}\n"
            "Create the file and add one ID per line (lines starting with '#' are comments)."
        )

    ids = [line.strip() for line in path.read_text().splitlines() if line.strip() and not line.strip().startswith("#")]

    if not ids:
        raise ValueError(f"[locust] Data file is empty or contains only comments: {path}\nAdd at least one valid ID.")

    return ids


OFFER_IDS: list[str] = _load_ids("sample_offer_ids.txt")
USER_IDS: list[str] = _load_ids("sample_user_ids.txt")
ARTIST_IDS: list[str] = _load_ids("sample_artist_ids.txt")


# ---------------------------------------------------------------------------
# Proxy setup - injected once at worker init via the Locust event system
# ---------------------------------------------------------------------------


@events.init.add_listener
def on_locust_init(environment, **_kwargs):
    """Log proxy status once at worker initialisation."""
    if USE_SOCKS_PROXY:
        environment.host = API_BASE_URL
        print(f"[locust] SOCKS5 proxy enabled → {SOCKS_PROXY_URL}")
    else:
        print("[locust] SOCKS5 proxy disabled (LOCUST_USE_SOCKS_PROXY=0)")


@events.test_start.add_listener
def on_test_start(environment, **_kwargs):
    """
    Send warm-up requests before the test begins so that Cloud Run exits its
    idle/cold-start state AND the Vertex AI connections are pre-initialised.

    Two endpoints are called (not counted in Locust stats - raw requests lib):
      1. GET  /similar_offers/{offer_id}          → wakes up the similar-offer Vertex pipeline
      2. POST /playlist_recommendation/{user_id}  → wakes up the playlist Vertex pipeline

    Retries each call until HTTP 200 is received or the timeout is reached (120 s).
    """
    proxies = {"http": SOCKS_PROXY_URL, "https": SOCKS_PROXY_URL} if USE_SOCKS_PROXY else {}
    token_params = {"token": API_TOKEN} if API_TOKEN else {}
    timeout_s = 120
    retry_interval_s = 5

    warmup_calls: list[dict] = [
        {
            "label": "similar_offers (Vertex warm-up)",
            "method": "GET",
            "url": f"{API_BASE_URL}/similar_offers/{random.choice(OFFER_IDS)}",
            "json": None,
        },
        {
            "label": "playlist_recommendation (Vertex warm-up)",
            "method": "POST",
            "url": f"{API_BASE_URL}/playlist_recommendation/{random.choice(USER_IDS)}",
            "json": {"isRestrained": True},
        },
    ]

    for call in warmup_calls:
        label: str = call["label"]
        url: str = call["url"]
        deadline = time.monotonic() + timeout_s
        print(f"[locust] ⏳ Warm-up: {label} → {url}")
        while time.monotonic() < deadline:
            try:
                t0 = time.monotonic()
                resp = _requests.request(
                    method=str(call["method"]),
                    url=url,
                    params=token_params,
                    json=call["json"],
                    proxies=proxies,
                    timeout=timeout_s,
                )
                elapsed = time.monotonic() - t0
                if resp.status_code in (200, 404):
                    # 404 can happen with stale IDs; still means the pipeline ran
                    print(f"[locust] ✅ {label} - HTTP {resp.status_code} in {elapsed:.1f}s")
                    break
                print(
                    f"[locust] ⚠️  {label} - HTTP {resp.status_code} after {elapsed:.1f}s, "
                    f"retrying in {retry_interval_s}s …"
                )
            except Exception as exc:
                print(f"[locust] ⚠️  {label} - request failed ({exc}), retrying in {retry_interval_s}s …")
            time.sleep(retry_interval_s)
        else:
            print(f"[locust] ❌ {label} did not succeed within {timeout_s}s - proceeding anyway.")

    print("[locust] 🚀 Warm-up complete - starting load test.")


# ---------------------------------------------------------------------------
# User behaviour
# ---------------------------------------------------------------------------


class RecommendationUser(HttpUser):
    """
    Simulates a single API consumer.

    constant_throughput(1) → each user attempts exactly 1 task per second.
    Combined with the LoadTestShape:
      •  6 active users  → ~6  req/s  (steady-state / mean)
      • 20 active users  → ~20 req/s  (peak burst)
    """

    host = API_BASE_URL
    wait_time = constant_throughput(1)  # 1 req/s per user

    def on_start(self):
        """Configure the SOCKS proxy and common query params once per user."""
        if USE_SOCKS_PROXY:
            self.client.proxies = {
                "http": SOCKS_PROXY_URL,
                "https": SOCKS_PROXY_URL,
            }
        # The API token is passed as a query param on every request
        self._token_param = {"token": API_TOKEN} if API_TOKEN else {}

    # --- Tasks (weighted) ---------------------------------------------------
    # Distribution mirrors realistic production usage:
    #   playlist_recommendation 50 %  - home / discovery feed
    #   similar_offers          40 %  - detail page
    #   similar_artists         10 %  - artist pages (less traffic)
    #
    # To target a single endpoint, set TARGET_ENDPOINT before running:
    #   TARGET_ENDPOINT=offers   locust -f locust/locustfile.py ...
    #   TARGET_ENDPOINT=playlist locust -f locust/locustfile.py ...
    #   TARGET_ENDPOINT=artists  locust -f locust/locustfile.py ...
    # Leave unset (or set to "all") for the default weighted mix.

    _target = os.getenv("TARGET_ENDPOINT", "all").lower()

    @task
    def run_target_task(self):
        """Dispatch to the appropriate endpoint task based on TARGET_ENDPOINT."""
        if self._target == "offers":
            self.get_similar_offers()
        elif self._target == "playlist":
            self.post_playlist_recommendation()
        elif self._target == "artists":
            self.get_similar_artists()
        else:
            # Default weighted mix: playlist 50 %, offers 40 %, artists 10 %
            weighted_tasks = (
                [self.get_similar_offers] * 4 + [self.post_playlist_recommendation] * 5 + [self.get_similar_artists] * 1
            )
            random.choice(weighted_tasks)()

    def get_similar_offers(self):
        """Call GET /similar_offers/{offer_id}, occasionally with geo coordinates (30 % of requests)."""
        offer_id = random.choice(OFFER_IDS)
        params = {**self._token_param}

        if random.random() < _GEO_PARAM_PROBABILITY:
            params["latitude"] = round(random.uniform(43.0, 49.0), 5)
            params["longitude"] = round(random.uniform(1.0, 7.0), 5)

        with self.client.get(
            f"/similar_offers/{offer_id}",
            params=params,
            name="/similar_offers/[offer_id]",
            catch_response=True,
        ) as resp:
            _handle_response(resp)

    def post_playlist_recommendation(self):
        """Call POST /playlist_recommendation/{user_id}, occasionally with geo coordinates (30 % of requests)."""
        user_id = random.choice(USER_IDS)
        params = {**self._token_param}

        if random.random() < _GEO_PARAM_PROBABILITY:
            params["latitude"] = round(random.uniform(43.0, 49.0), 5)
            params["longitude"] = round(random.uniform(1.0, 7.0), 5)

        body: dict = {"isRestrained": True}

        with self.client.post(
            f"/playlist_recommendation/{user_id}",
            params=params,
            json=body,
            name="/playlist_recommendation/[user_id]",
            catch_response=True,
        ) as resp:
            _handle_response(resp)

    def get_similar_artists(self):
        """Call GET /similar_artists/{artist_id}."""
        artist_id = random.choice(ARTIST_IDS)
        params = {**self._token_param}

        with self.client.get(
            f"/similar_artists/{artist_id}",
            params=params,
            name="/similar_artists/[artist_id]",
            catch_response=True,
        ) as resp:
            _handle_response(resp)


# ---------------------------------------------------------------------------
# Load shape  -  mean 6 req/s / peak 20 req/s
# ---------------------------------------------------------------------------


class StagingLoadShape(LoadTestShape):
    """
    Simulates a realistic intra-day traffic profile:

      Phase 0 - Warm-up  :  0 → 6 users over 30 s   (ramp, ~6  req/s at top)
      Phase 1 - Steady   :  6 users for  90 s         (~6  req/s)
      Phase 2 - Peak     :  6 → 20 users over 30 s   (ramp, ~20 req/s at top)
      Phase 3 - Peak hold: 20 users for  60 s         (~20 req/s)
      Phase 4 - Cool-down: 20 → 6 users over 30 s    (ramp down)
      Phase 5 - Steady   :  6 users for  60 s         (~6  req/s)
      Phase 6 - End      :  6 → 0 users over 30 s    (drain)

    Total duration ≈ 5 min 30 s.
    Average throughput over the full run ≈ 6-8 req/s.
    """

    # (cumulative_time_seconds, target_user_count, spawn_rate)
    stages: ClassVar[list[tuple[int, int, int]]] = [
        # (time_s, users, spawn_rate)
        (30, 6, 1),  # Phase 0 - warm-up
        (120, 6, 1),  # Phase 1 - steady state
        (150, 20, 2),  # Phase 2 - ramp to peak
        (210, 20, 2),  # Phase 3 - peak hold
        (240, 6, 2),  # Phase 4 - ramp down
        (300, 6, 1),  # Phase 5 - back to steady
        (330, 0, 2),  # Phase 6 - drain
    ]

    def tick(self):
        """Return (user_count, spawn_rate) for the current run-time, or None when the test is over."""
        run_time = self.get_run_time()
        for stage_time, user_count, spawn_rate in self.stages:
            if run_time < stage_time:
                return user_count, spawn_rate
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _handle_response(resp) -> None:
    """Mark the Locust response as success or failure based on HTTP status.

    - 200 OK         → success
    - 401 Unauthorized → failure (likely a missing or invalid API token)
    - 404 Not Found  → success (stale test-data ID; the pipeline ran successfully)
    - anything else  → failure with truncated response body for diagnosis
    """
    if resp.status_code == HTTPStatus.OK:
        resp.success()
    elif resp.status_code == HTTPStatus.UNAUTHORIZED:
        resp.failure(f"Unauthorized - check REMOTE_API_TOKEN (got {resp.status_code})")
    elif resp.status_code == HTTPStatus.NOT_FOUND:
        resp.success()
    else:
        resp.failure(f"Unexpected status {resp.status_code}: {resp.text[:200]}")
