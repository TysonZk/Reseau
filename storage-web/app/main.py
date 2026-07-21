"""Application Flask — dashboard web des informations de stockage (port 8888)."""

from __future__ import annotations

import os

from flask import Flask, jsonify, render_template

from . import alerts
from .collectors import collect

app = Flask(__name__)

# Démarre la surveillance des alertes par webhook (no-op si non configuré)
alerts.start_monitor()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/storage")
def api_storage():
    return jsonify(collect())


@app.route("/api/config")
def api_config():
    return jsonify({"alerts": alerts.config()})


@app.route("/api/test-webhook", methods=["POST"])
def api_test_webhook():
    if not alerts.enabled():
        return jsonify({"ok": False, "error": "Aucun webhook configuré (ALERT_WEBHOOK_URL)."}), 400
    ok = alerts.send_test()
    return jsonify({"ok": ok}), (200 if ok else 502)


@app.route("/healthz")
def healthz():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8888"))
    app.run(host="0.0.0.0", port=port, debug=False)
