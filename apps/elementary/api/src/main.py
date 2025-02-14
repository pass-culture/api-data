from constants import DATA_BUCKET_NAME
from flask import Flask
from utils import download_blob, get_latest_file

app = Flask(__name__)


@app.route("/")
def serve_static_file():
    report_file = get_latest_file(DATA_BUCKET_NAME)
    html_content = download_blob(DATA_BUCKET_NAME, report_file)
    return html_content


@app.route("/health")
def check_health():
    return "OK", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=8081)
