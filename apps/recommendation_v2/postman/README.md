# Postman / Newman — Recommendation API V2

This folder holds a Postman collection to exercise the Recommendation API V2, both locally and against the remote `dev` / `stg` / `prod` environments.

> ℹ️ All `make` commands below must be run from the app root (`apps/recommendation_v2/`), which is also where the `newman` paths (`postman/...`) resolve from.

## Files

* `api_reco_v2.postman_collection.json` — the shared request collection.
* `api_reco_v2.postman_environment.json` — a single shared environment holding sample values (`user_id`, `offer_id`, `artist_id`), with `base_url` and `token` left empty.

> ⚠️ `base_url` and `token` are secrets. They are supplied per run: `make postman-run` reads `REMOTE_API_URL` and ``REMOTE_API_TOKEN`` from your `.env.<env>`. The environment you target is selected by `DEPLOY_ENV`.

## Reaching a remote API

Remote APIs are not reachable directly from your machine, they sit behind the VPC. To call them from the **Postman app** or **Newman** (the Postman CLI), you first open an **HTTP** proxy tunnel, then point your HTTP client at it.

```bash
make http-proxy-tunnel DEPLOY_ENV=dev   # or stg / prod
```

This command:

* Connects to the IAP bastion VM (`tinyproxy-*`) through gcloud Identity-Aware Proxy.
* Forwards your **local** port `REMOTE_API_SOCKS_PORT` (default `1080`) to the **tinyproxy HTTP proxy** running on the bastion at `BASTION_HTTP_PROXY_PORT` (default `8888`). Both are set in your `.env.<env>` file.
* Leaves an HTTP proxy listening at `http://localhost:1080`. Keep this terminal open; press `Ctrl+C` to close the tunnel.

> 💡 **Why an HTTP proxy and not SOCKS?** Postman can use a SOCKS5 proxy directly (Settings → Proxy, `socks5`/`socks5h`), but Newman cannot — it would require installing and configuring a `proxychains` wrapper. An HTTP proxy works the same way for both Postman and Newman, so it's the simpler common path.

## Option A: Newman via `make` (recommended)

One command opens the HTTP tunnel, fetches the token, runs the collection, and tears the tunnel down on exit:

```bash
make postman-run DEPLOY_ENV=dev   # or stg / prod
```

Requires `newman` installed (`npm install -g newman`); `BASTION_HTTP_PROXY_PORT`, `REMOTE_API_URL`, `GCP_SECRET_PROJECT`, and `API_RECO_TOKEN_SECRET_NAME` set in the matching `.env.<env>`.

## Option B: Newman manually (two terminals)

If you prefer to manage the tunnel yourself, open it in one terminal (`make http-proxy-tunnel DEPLOY_ENV=dev`), then in a **second terminal** route Newman through the proxy and pass `base_url`/`token` explicitly:

```bash
TOKEN=$(make -s get-api-token DEPLOY_ENV=dev)

HTTP_PROXY=http://localhost:1080 \
HTTPS_PROXY=http://localhost:1080 \
newman run postman/api_reco_v2.postman_collection.json \
  --environment postman/api_reco_v2.postman_environment.json \
  --env-var "base_url=<remote API URL, e.g. REMOTE_API_URL from .env.dev>" \
  --env-var "token=$TOKEN"
```

Swap `DEPLOY_ENV` and `base_url` to target `stg` or `prod`.

## Option C: Postman app (GUI)

1. Start the tunnel: `make http-proxy-tunnel DEPLOY_ENV=dev`.
2. In Postman, go to **Settings → Proxy → Add a custom proxy configuration** and set the proxy server to `localhost` port `1080` (enable it for both HTTP and HTTPS).
3. Import the collection and `api_reco_v2.postman_environment.json`, select it, then fill in `base_url` (the remote API URL) and `token` for the environment you're targeting, and send requests as usual.

## Option D: Local API (no tunnel)

When the API is running locally (`make start-with-remote-db` or `make start`), there is no bastion and no proxy — point Newman straight at the local server. No `HTTP_PROXY` and no token are needed:

```bash
newman run postman/api_reco_v2.postman_collection.json \
  --environment postman/api_reco_v2.postman_environment.json \
  --env-var "base_url=http://127.0.0.1:8801"
```

Match `base_url`'s port to `FASTAPI_SERVER_PORT` in your `.env`. If your local API requires a token, add `--env-var "token=<token>"`.

## Troubleshooting

> 💡 **"tunneling socket could not be established"?** Newman/Postman couldn't reach the proxy on `localhost:1080`. The two usual causes:
> 1. **The tunnel isn't ready yet.** The IAP tunnel takes ~6–10s to start listening.
> 2. **Wrong remote port.** `BASTION_HTTP_PROXY_PORT` must match the port tinyproxy listens on (`8888`). Confirm it on the bastion:
>    ```bash
>    gcloud compute ssh <bastion> --zone <zone> --project <project> --tunnel-through-iap \
>      -- 'sudo ss -tlnp | grep tinyproxy'
>    ```
