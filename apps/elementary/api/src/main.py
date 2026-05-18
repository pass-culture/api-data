from flask import Flask
from utils import download_blob, get_latest_file

app = Flask(__name__)


@app.route("/")
def serve_static_file() -> bytes:
    report_file = get_latest_file()
    if report_file is None:
        return b"No report available", 404
    html_content = download_blob(report_file)
    return html_content


@app.route("/health")
def check_health() -> tuple[str, int]:
    return "OK", 200


if __name__ == "__main__":
    app.run()
