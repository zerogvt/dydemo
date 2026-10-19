"""
Sample backend Flask application.

Holds every endpoint of the demo; the gateway in front of it is a plain
reverse proxy. Each endpoint simulates a different failure mode, for
generating observability signals.
"""

import logging
import os
import uuid
from logging.config import dictConfig
from random import randint
from time import sleep

from flask import Flask, g, has_app_context, jsonify, request

bapp = Flask(__name__)

# Correlation ID shared by the gateway and the backend. The gateway sets it (or
# passes on the caller's), and every log line and response carries it, so one
# call can be followed across both services and the loadgen output.
REQUEST_ID_HEADER = "X-Request-ID"


# Stamps every log record with the current request's ID, '-' outside a
# request. Done at record creation rather than in a handler filter, so it covers
# every logger and handler, including ones added later.
_make_record = logging.getLogRecordFactory()


def _record_with_request_id(*args, **kwargs):
    record = _make_record(*args, **kwargs)
    record.request_id = g.get("request_id", "-") if has_app_context() else "-"
    return record


logging.setLogRecordFactory(_record_with_request_id)


dictConfig(
    {
        "version": 1,
        "formatters": {
            "default": {
                "format": "[%(asctime)s] %(levelname)s in %(module)s "
                "[request_id=%(request_id)s]: %(message)s",
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


@bapp.before_request
def assign_request_id():
    g.request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex


@bapp.after_request
def return_request_id(response):
    response.headers[REQUEST_ID_HEADER] = g.request_id
    return response


@bapp.route("/")
def hello_world():
    bapp.logger.info("Hello, World! endpoint was reached")
    return "Successful response\n", 200


@bapp.route("/server_error")
def server_error():
    bapp.logger.info("Server Error endpoint was reached")
    return "Server error\n", 500


@bapp.route("/client_error")
def client_error():
    bapp.logger.info("Client Error endpoint was reached")
    return "Client error\n", 400


@bapp.route("/latency")
def latency():
    rn = randint(1, 100)
    # 90 percententile latency of 2 seconds
    if rn > 90 and rn <= 99:
        sleep(2)
    # 99 percententile latency of 5 seconds
    elif rn > 99:
        sleep(5)
    return f"Latency endpoint {rn}\n", 200


@bapp.route("/blowup")
def blowup():
    rn = randint(1, 10)
    bapp.logger.info("blowup endpoint was reached")
    # 30% chance to crash. os._exit, not sys.exit: gunicorn catches SystemExit
    # and answers a tidy 500 from a worker that carries on. os._exit kills the
    # worker process on the spot, so the connection drops, the gateway answers
    # 502, and the gunicorn master boots a replacement worker.
    if rn > 7:
        bapp.logger.info("crashing...")
        os._exit(1)
    return "Survived blowup\n", 200


@bapp.route("/transaction", methods=["GET", "POST"])
def transaction():
    # A business transaction ID, distinct from the request ID: it names the
    # record this call "creates", the request ID names the call itself.
    data = {"transaction_id": uuid.uuid1().hex, "request_id": g.request_id}
    bapp.logger.info("transaction %s created", data["transaction_id"])
    return jsonify(data), 201


if __name__ == "__main__":
    bapp.run(debug=True)
