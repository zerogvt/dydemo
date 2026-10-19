"""
Tests for the gateway's proxying. The backend is mocked out, so these run on
their own. Standard library only: `python -m unittest` from this directory.
"""

import unittest
from unittest import mock

import requests

import gateway


def backend_response(status=200, body=b"ok", headers=None):
    r = requests.Response()
    r.status_code = status
    r._content = body
    r.headers.update(headers or {})
    return r


@mock.patch("gateway.requests.request")
class GatewayTest(unittest.TestCase):
    def setUp(self):
        self.client = gateway.wapp.test_client()

    def test_forwards_method_path_query_and_body(self, request):
        request.return_value = backend_response(201, b'{"a": 1}')
        r = self.client.post("/transaction?x=1", data=b"payload")
        method, url = request.call_args.args
        kwargs = request.call_args.kwargs
        self.assertEqual((method, url), ("POST", "http://dydemo-backend-service/transaction"))
        self.assertEqual(kwargs["params"].to_dict(), {"x": "1"})
        self.assertEqual(kwargs["data"], b"payload")
        self.assertEqual((r.status_code, r.data), (201, b'{"a": 1}'))

    def test_root_path(self, request):
        request.return_value = backend_response()
        self.client.get("/")
        self.assertEqual(request.call_args.args[1], "http://dydemo-backend-service/")

    def test_relays_backend_errors_unchanged(self, request):
        request.return_value = backend_response(500, b"Server error\n")
        r = self.client.get("/server_error")
        self.assertEqual((r.status_code, r.data), (500, b"Server error\n"))

    def test_timeout_is_504(self, request):
        request.side_effect = requests.exceptions.Timeout()
        self.assertEqual(self.client.get("/latency").status_code, 504)

    def test_dropped_connection_is_502(self, request):
        request.side_effect = requests.exceptions.ConnectionError()
        self.assertEqual(self.client.get("/blowup").status_code, 502)

    def test_request_id_generated_and_forwarded(self, request):
        request.return_value = backend_response()
        r = self.client.get("/")
        sent = request.call_args.kwargs["headers"]["X-Request-ID"]
        self.assertEqual(len(sent), 32)
        self.assertEqual(r.headers["X-Request-ID"], sent)

    def test_request_id_from_caller_kept(self, request):
        request.return_value = backend_response()
        r = self.client.get("/", headers={"X-Request-ID": "abc"})
        self.assertEqual(request.call_args.kwargs["headers"]["X-Request-ID"], "abc")
        self.assertEqual(r.headers["X-Request-ID"], "abc")

    def test_request_id_on_gateway_errors(self, request):
        request.side_effect = requests.exceptions.ConnectionError()
        r = self.client.get("/", headers={"X-Request-ID": "abc"})
        self.assertEqual(r.headers["X-Request-ID"], "abc")

    def test_does_not_forward_host_or_trace_context(self, request):
        request.return_value = backend_response()
        self.client.get("/", headers={"traceparent": "00-x-y-01", "X-Dynatrace": "z"})
        sent = {k.lower() for k in request.call_args.kwargs["headers"]}
        self.assertFalse(sent & {"host", "traceparent", "x-dynatrace"})

    def test_does_not_return_stale_length_or_encoding(self, request):
        request.return_value = backend_response(
            headers={"Content-Encoding": "gzip", "Content-Length": "999", "X-Other": "1"})
        r = self.client.get("/")
        self.assertNotIn("Content-Encoding", r.headers)
        self.assertEqual(r.headers["Content-Length"], "2")
        self.assertEqual(r.headers["X-Other"], "1")


if __name__ == "__main__":
    unittest.main()
