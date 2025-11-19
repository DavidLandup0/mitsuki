"""Flask hello world benchmark app."""

import logging

from flask import Flask, jsonify

log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)
app = Flask(__name__)


@app.route("/")
def hello():
    return jsonify({"message": "Hello, World!"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
