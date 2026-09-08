"""
A sample flask web app that simulates various response codes and latencies.
"""

import os
from random import randint
import sys
from time import sleep
import uuid
from logging.config import dictConfig
import requests
from flask import Flask

wapp = Flask(__name__)

# Where /transaction forwards to. Overridable via env so the same image runs
# in-cluster and on a laptop (e.g. BACKEND_URL=http://127.0.0.1:5000/).
# The default is the namespace-relative Service name rather than a full
# .svc.cluster.local FQDN: it resolves through the pod's DNS search path, so
# it keeps working if this app is deployed into a different namespace.
BACKEND_URL = os.environ.get("BACKEND_URL", "http://dydemo-backend-service/")

# Seconds to wait on the backend before giving up. Without a timeout a hung
# backend pins a gunicorn worker forever, and with only 2 workers a couple of
# stuck requests take the whole gateway down. Tune it down (or point
# BACKEND_URL at something slow) to demo timeout behaviour on purpose.
BACKEND_TIMEOUT = float(os.environ.get("BACKEND_TIMEOUT", "5"))


dictConfig(
    {
        "version": 1,
        "formatters": {
            "default": {
                "format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
            },
        },
        "handlers": {
            "wsgi": {
                "class": "logging.StreamHandler",
                "stream": "ext://flask.logging.wsgi_errors_stream",
                "formatter": "default",
            },
        },
        "root": {
            "level": "INFO",
            "handlers": ["wsgi"],
        },
    }
)


@wapp.route("/")
def hello_world():
    wapp.logger.info("Hello, World! endpoint was reached")
    return "Successful response\n", 200


@wapp.route("/server_error")
def server_error():
    wapp.logger.info("Server Error endpoint was reached")
    return "Server error\n", 500


@wapp.route("/client_error")
def client_error():
    wapp.logger.info("Client Error endpoint was reached")
    return "Client error\n", 400


@wapp.route("/latency")
def latency():
    rn = randint(1, 100)
    # 90 percententile latency of 2 seconds
    if rn > 90 and rn <= 99:
        sleep(2)
    # 99 percententile latency of 5 seconds
    elif rn > 99:
        sleep(5)
    return f"Latency endpoint {rn}\n", 200


@wapp.route("/blowup")
def blowup():
    rn = randint(1, 10)
    wapp.logger.info("blowup endpoint was reached")
    # 30% chance to crash
    if rn > 7:
        wapp.logger.info("crashing...")
        sys.exit(1)
    return "Survived blowup\n", 200


@wapp.route("/transaction")
def transaction():
    data = {"transaction_id": uuid.uuid1().hex}
    wapp.logger.info("transaction endpoint was reached, forwarding to %s", BACKEND_URL)
    try:
        response = requests.post(BACKEND_URL, json=data, timeout=BACKEND_TIMEOUT)
    except requests.exceptions.Timeout:
        # Map to the status codes a gateway is supposed to use, so a backend
        # problem is distinguishable from this app's own /server_error rather
        # than surfacing as an opaque Flask 500.
        wapp.logger.error("backend %s timed out after %ss", BACKEND_URL, BACKEND_TIMEOUT)
        return "Backend timed out\n", 504
    except requests.exceptions.RequestException as exc:
        wapp.logger.error("backend %s unreachable: %s", BACKEND_URL, exc)
        return "Backend unreachable\n", 502
    return f"{response.text}\n", response.status_code


if __name__ == "__main__":
    wapp.run(debug=True)
