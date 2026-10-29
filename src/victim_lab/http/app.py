import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone

from flask import Flask, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from victim_lab.syslog.probe import send_probe
from victim_lab.syslog.reader import dashboard_status


def required_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


app = Flask(__name__)
app.secret_key = required_env("FLASK_SECRET_KEY")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
username = required_env("VICTIM_USERNAME")
password_hash = required_env("VICTIM_PASSWORD_HASH")
experiment_id = os.environ.get("EXPERIMENT_ID", "unlabeled")

access_logger = logging.getLogger("victim.access")
access_logger.setLevel(logging.INFO)
access_logger.propagate = False
if not access_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    access_logger.addHandler(handler)


@app.before_request
def start_request():
    g.started_at = time.monotonic()
    g.request_id = uuid.uuid4().hex


@app.after_request
def log_request(response):
    response.headers["X-Request-ID"] = g.request_id
    entry = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_id": experiment_id,
        "request_id": g.request_id,
        "remote_addr": request.remote_addr,
        "method": request.method,
        "route": request.url_rule.rule if request.url_rule else "<unmatched>",
        "status": response.status_code,
        "response_bytes": response.calculate_content_length(),
        "duration_ms": round((time.monotonic() - g.started_at) * 1000, 3),
    }
    access_logger.info(json.dumps(entry, ensure_ascii=False, separators=(",", ":")))
    return response


@app.get("/healthz")
def healthz():
    return jsonify(status="ok", service="victim-http")


@app.get("/")
def index():
    return redirect(url_for("dashboard" if session.get("logged_in") else "login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    error = None
    if request.method == "POST":
        submitted_username = request.form.get("username", "")
        submitted_password = request.form.get("password", "")
        if submitted_username == username and check_password_hash(
            password_hash, submitted_password
        ):
            session.clear()
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        error = "Tên đăng nhập hoặc mật khẩu không đúng."
    return render_template("login.html", error=error)


@app.get("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template(
        "dashboard.html", username=username, syslog_host=os.environ.get("SYSLOG_HOST", "10.20.0.2")
    )


@app.get("/api/syslog/status")
def syslog_status():
    if not session.get("logged_in"):
        return jsonify(error="unauthorized"), 401
    try:
        return jsonify(dashboard_status())
    except Exception as exc:
        app.logger.warning("Syslog status unavailable: %s", exc)
        return jsonify(error="Syslog metrics unavailable"), 503


@app.post("/api/syslog/probe")
def syslog_probe():
    if not session.get("logged_in"):
        return jsonify(error="unauthorized"), 401
    try:
        probe_id = send_probe(os.environ.get("SYSLOG_HOST", "10.20.0.2"))
        return jsonify(probe_id=probe_id, status="sent_unconfirmed")
    except OSError as exc:
        app.logger.warning("Syslog probe unavailable: %s", exc)
        return jsonify(error="Unable to send Syslog probe"), 503


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))
