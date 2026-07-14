from flask import Flask, jsonify
from datetime import datetime, timezone
import os

app = Flask(__name__)


APP_VERSION = os.getenv("APP_VERSION", "1.0.0")


@app.route("/")
def index():
    return jsonify({
        "application": "AutoDeploy CI/CD Platform",
        "status": "running",
        "version": APP_VERSION
    }), 200


@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "version": APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
