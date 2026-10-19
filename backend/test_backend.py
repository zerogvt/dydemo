"""
Tests for the backend endpoints. Standard library only:
`python -m unittest` from this directory.
"""

import unittest
from unittest import mock

import backend


class BackendTest(unittest.TestCase):
    def setUp(self):
        self.client = backend.bapp.test_client()

    def test_root(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)

    def test_server_error(self):
        self.assertEqual(self.client.get("/server_error").status_code, 500)

    def test_client_error(self):
        self.assertEqual(self.client.get("/client_error").status_code, 400)

    @mock.patch("backend.sleep")
    @mock.patch("backend.randint", return_value=100)
    def test_latency_tail(self, _randint, sleep):
        r = self.client.get("/latency")
        self.assertEqual(r.status_code, 200)
        sleep.assert_called_once_with(5)

    @mock.patch("backend.sleep")
    @mock.patch("backend.randint", return_value=50)
    def test_latency_fast(self, _randint, sleep):
        self.assertEqual(self.client.get("/latency").status_code, 200)
        sleep.assert_not_called()

    @mock.patch("backend.randint", return_value=1)
    def test_blowup_survives(self, _randint):
        self.assertEqual(self.client.get("/blowup").status_code, 200)

    @mock.patch("backend.os._exit")
    @mock.patch("backend.randint", return_value=10)
    def test_blowup_crashes(self, _randint, exit_):
        self.client.get("/blowup")
        exit_.assert_called_once_with(1)

    def test_transaction(self):
        for method in (self.client.get, self.client.post):
            r = method("/transaction", headers={"X-Request-ID": "abc"})
            self.assertEqual(r.status_code, 201)
            self.assertEqual(r.json["request_id"], "abc")
            self.assertEqual(len(r.json["transaction_id"]), 32)

    def test_request_id_passed_through(self):
        r = self.client.get("/", headers={"X-Request-ID": "abc"})
        self.assertEqual(r.headers["X-Request-ID"], "abc")

    def test_request_id_generated(self):
        r = self.client.get("/")
        self.assertEqual(len(r.headers["X-Request-ID"]), 32)

    def test_request_id_in_logs(self):
        with self.assertLogs(backend.bapp.logger, "INFO") as logs:
            self.client.get("/", headers={"X-Request-ID": "abc"})
        self.assertEqual(logs.records[0].request_id, "abc")


if __name__ == "__main__":
    unittest.main()
