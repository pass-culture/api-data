import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from time import sleep
from urllib.parse import parse_qs, urlparse
from webbrowser import open_new_tab

import requests
from google.auth import default
from google.cloud import secretmanager

SERVER_HTTP_PORT = 4444
IAP_REFRESH_TOKEN_ENV_NAME = "IAP_REFRESH_TOKEN"
PROJECT_ID = default()[1]


def access_secret(secret_id):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")


class MyHandlerForHTTP(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()

        # Parse the URL and query parameters
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)

        # Extract the 'code' parameter if it exists
        code = query_params.get("code", [None])[0]

        if code:
            self.server.output = code
        else:
            self.server.output = "Code not found"


def start_server(output):
    server_address = ("", SERVER_HTTP_PORT)
    with HTTPServer(server_address, MyHandlerForHTTP) as httpd:
        httpd.handle_request()
        output[0] = httpd.output


def get_auth_code(client_id):
    output = [None]
    t = Thread(target=start_server, args=(output,))
    t.start()
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={client_id}&response_type=code&scope=openid%20email&access_type=offline&redirect_uri=http://localhost:{SERVER_HTTP_PORT}&cred_ref=true"
    open_new_tab(auth_url)
    sleep(1)
    t.join()
    return output[0]


def get_refresh_token_from_oauth(auth_code, client_id, client_secret):
    oauth_token_base_URL = "https://oauth2.googleapis.com/token"
    payload = {
        "code": auth_code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": f"http://localhost:{SERVER_HTTP_PORT}",
        "grant_type": "authorization_code",
    }
    res = requests.post(oauth_token_base_URL, data=payload, verify=False)
    return str(json.loads(res.text)["refresh_token"])


print(f"Getting IAP refresh token for GCP project {PROJECT_ID}...")
dekstop_app_client_id = access_secret("iap_login_client_id")
desktop_app_secret = access_secret("iap_login_secret")
auth_code = get_auth_code(dekstop_app_client_id)
refresh_token = get_refresh_token_from_oauth(
    auth_code, dekstop_app_client_id, desktop_app_secret
)
print(f"IAP refresh token fetched: {refresh_token}")


# Path to .zshrc
shell = os.getenv("SHELL")
if "zsh" in shell:
    rc_file = os.path.expanduser("~/.zshrc")
elif "bash" in shell:
    rc_file = os.path.expanduser("~/.bashrc")
else:
    raise OSError("Unsupported shell. Only Zsh and Bash are supported.")
print(f"Writing IAP refresh token to {rc_file}...")

# Read the contents of .zshrc
with open(rc_file) as file:
    lines = file.readlines()

# Check if the line exists and replace it, otherwise append it
with open(rc_file, "w") as file:
    token_line = f"export {IAP_REFRESH_TOKEN_ENV_NAME}={refresh_token}\n"
    found = False
    for line in lines:
        if line.startswith(f"export {IAP_REFRESH_TOKEN_ENV_NAME}="):
            file.write(token_line)
            found = True
        else:
            file.write(line)
    if not found:
        file.write(token_line)
        file.write("\n")
print(f"Writing IAP refresh written in {rc_file} as '{IAP_REFRESH_TOKEN_ENV_NAME}'")
