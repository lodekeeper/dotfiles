#!/usr/bin/env python3
"""Regression checks for schema-driven Dora evidence collection (no network)."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("fetch-dora-snapshot.py")
SPEC = importlib.util.spec_from_file_location("dora_snapshot", SCRIPT)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def schema():
    return {"swagger": "2.0", "basePath": "/api", "host": "ignored.invalid",
            "paths": {"/relocated/clients": {"get": {"operationId": "getConsensusClients"}},
                      "/relocated/forks": {"get": {"operationId": "getNetworkClientHeadForks"}}}}


CLIENTS = {"clients": [{"client_name": "one", "status": "offline", "last_error": "TLS"}], "count": 1}
FORKS = {"status": "OK", "data": {"forks": [], "fork_count": 0}}


class DoraSnapshotTests(unittest.TestCase):
    def test_advertised_ids_and_base_path_not_guessed_routes(self):
        self.assertEqual(M.discover_paths(schema()), {
            "clients": "/api/relocated/clients", "forks": "/api/relocated/forks"})

    def test_missing_duplicate_and_post_only_operations_fail(self):
        for kind in ("missing", "duplicate", "post"):
            with self.subTest(kind=kind):
                s = schema()
                operation = s["paths"].pop("/relocated/clients")
                if kind == "duplicate":
                    s["paths"]["/one"] = operation
                    s["paths"]["/two"] = operation
                elif kind == "post":
                    s["paths"]["/one"] = {"post": operation["get"]}
                with self.assertRaises(M.SnapshotError):
                    M.discover_paths(s)

    def test_schema_and_parameter_changes_fail_closed(self):
        for location in ("path", "operation"):
            for params in ([{"required": True}], [{"$ref": "#/parameters/token"}], None):
                with self.subTest(location=location, params=params):
                    s = schema()
                    owner = s["paths"]["/relocated/clients"]
                    if location == "operation":
                        owner = owner["get"]
                    owner["parameters"] = params
                    with self.assertRaises(M.SnapshotError):
                        M.discover_paths(s)
        for s in (None, {}, {"swagger": "3.0"}, {"swagger": "2.0", "paths": []}):
            with self.assertRaises(M.SnapshotError):
                M.discover_paths(s)

    def test_schema_cannot_redirect_or_template_api_requests(self):
        for path in ("//other.example/api", "https://other.example", "/a/../b", "/a/{id}", "/a?q=1", "/a#x", "/a%2fb"):
            with self.subTest(path=path):
                s = schema()
                s["paths"][path] = s["paths"].pop("/relocated/clients")
                with self.assertRaises(M.SnapshotError):
                    M.discover_paths(s)
                s = schema()
                s["basePath"] = path
                with self.assertRaises(M.SnapshotError):
                    M.discover_paths(s)

    def test_only_explicit_https_origin_without_credentials(self):
        self.assertEqual(M.dora_origin({"dora": "https://example.com:443/"}), "https://example.com:443")
        for value in (None, "http://example.com", "https://u:p@example.com", "https://example.com/x", "https://example.com?x", "https://example.com#x", "https://example.com:bad", "https://example.com:0", "https://example.com\n"):
            with self.subTest(value=value), self.assertRaises(M.SnapshotError):
                M.dora_origin({"dora": value})

    def test_transport_success_never_means_client_or_network_healthy(self):
        with patch.object(M, "fetch_json", side_effect=[schema(), CLIENTS, FORKS]) as fetch:
            bundle = M.collect_snapshot("https://actual.example", 9)
        self.assertTrue(bundle["transportOk"])
        self.assertNotIn("healthy", bundle)
        self.assertEqual(bundle["clients"], CLIENTS)
        self.assertEqual(bundle["counts"], {"clients": 1, "forks": 0})
        self.assertTrue(all(call.args[0].startswith("https://actual.example/") for call in fetch.call_args_list))

    def test_invalid_clients_and_forks_never_produce_bundle(self):
        for clients in (None, {}, {"clients": None, "count": 0}, {"clients": [None], "count": 1},
                        {"clients": [], "count": True}, {"clients": [], "count": -1},
                        {"clients": [], "count": 1}, dict(CLIENTS, status="ERROR")):
            with self.subTest(clients=clients), patch.object(M, "fetch_json", side_effect=[schema(), clients, FORKS]), self.assertRaises(M.SnapshotError):
                M.collect_snapshot("https://example.com", 5)
        for forks in (None, {}, {"status": "ERROR", "data": FORKS["data"]}, {"status": "OK", "data": None},
                      {"status": "OK", "data": {"forks": [], "fork_count": False}},
                      {"status": "OK", "data": {"forks": "oops", "fork_count": 0}}):
            with self.subTest(forks=forks), patch.object(M, "fetch_json", side_effect=[schema(), CLIENTS, forks]), self.assertRaises(M.SnapshotError):
                M.collect_snapshot("https://example.com", 5)

    def test_curl_failures_and_invalid_json(self):
        for code, body in ((22, b"{}"), (0, b"<html>error</html>"), (0, b"\xff"), (0, b'{"value":NaN}'), (0, b'{"value":1e999}')):
            with self.subTest(code=code, body=body), patch.object(M.subprocess, "run", return_value=subprocess.CompletedProcess([], code, body + b"\n200", b"")), self.assertRaises(M.SnapshotError):
                M.fetch_json("https://example.com", 1)
        for error in (FileNotFoundError(), subprocess.TimeoutExpired("curl", 1)):
            with patch.object(M.subprocess, "run", side_effect=error), self.assertRaises(M.SnapshotError):
                M.fetch_json("https://example.com", 1)

    def test_valid_json_on_redirect_is_not_success(self):
        for status in (b"301", b"302", b"204", b"500", b""):
            with self.subTest(status=status), patch.object(M.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, b'{}\n' + status, b"")), self.assertRaises(M.SnapshotError):
                M.fetch_json("https://example.com", 1)
        with patch.object(M.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, b'{}\n200', b"")):
            self.assertEqual(M.fetch_json("https://example.com", 1), {})

    def test_cli_complete_bundle_or_no_stdout_after_later_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inventory = root / "endpoints.json"
            inventory.write_text(json.dumps({"dora": "https://actual.example"}))
            curl = root / "curl"
            fixtures = {"/api/swagger/doc.json": schema(), "/api/relocated/clients": CLIENTS, "/api/relocated/forks": FORKS}
            curl.write_text(f"#!{sys.executable}\n" +
                            "import json, os, sys\nfrom urllib.parse import urlsplit\n" +
                            "with open(os.environ['DORA_TEST_TRACE'], 'a') as f: f.write(json.dumps(sys.argv[1:])+'\\n')\n" +
                            "path=urlsplit(sys.argv[-1]).path\n" +
                            "if os.environ.get('DORA_TEST_FAIL') and path.endswith('/forks'): sys.exit(22)\n" +
                            f"sys.stdout.write(json.dumps({fixtures!r}[path])+'\\n200')\n")
            curl.chmod(0o700)
            trace = root / "trace.jsonl"
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ.get("PATH", ""), DORA_TEST_TRACE=str(trace))
            command = [sys.executable, str(SCRIPT), "--endpoints-json", str(inventory)]
            result = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["counts"], {"clients": 1, "forks": 0})
            requests = [json.loads(line) for line in trace.read_text().splitlines()]
            self.assertEqual(len(requests), 3)
            for args in requests:
                self.assertEqual(args[0], "-q")
                self.assertNotIn("--location", args)
                self.assertNotIn("-L", args)
                self.assertTrue(args[-1].startswith("https://actual.example/"))
            result = subprocess.run(command, env=dict(env, DORA_TEST_FAIL="1"), capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertIn("curl exit 22", result.stderr)
            inventory.write_text("private invalid JSON")
            result = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertNotIn("private", result.stderr)


if __name__ == "__main__":
    unittest.main()
