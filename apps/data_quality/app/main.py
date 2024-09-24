from flask import Flask
from utils import DATA_BUCKET_NAME, download_blob, get_latest_file

app = Flask(__name__)

report_file = get_latest_file(DATA_BUCKET_NAME)
html_content = download_blob(DATA_BUCKET_NAME, report_file)


@app.route("/")
def serve_static_file():
    return html_content


if __name__ == "__main__":
    app.run(host="localhost", port=8080)
