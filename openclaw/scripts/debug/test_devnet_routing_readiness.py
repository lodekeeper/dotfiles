#!/usr/bin/env python3
"""Routing regressions: distinguish unavailable discovery from absent devnets."""
import importlib.util
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch


SOURCE = Path(os.environ.get("DEVNET_ROUTING_TEST_SOURCE", str(
    Path(__file__).with_name("check-devnet-routing-readiness.py")
)))
SPEC = importlib.util.spec_from_file_location("routing_readiness", SOURCE)
routing = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(routing)


class RoutingTests(unittest.TestCase):
    def route(self, target, *, networks=None, local=None, panda=None, reply=None):
        if networks is None:
            networks = [{"id": "focil-devnet-1", "status": "active", "name": "devnet-1"}]
        if reply is None:
            reply = (0, json.dumps({"networks": networks}), "")
        with patch.object(routing, "collect_kurtosis_enclaves", return_value=(
            local or {"state": "ready", "names": []}
        )), patch.object(routing, "collect_panda_datasources", return_value=(
            panda or {"state": "ready", "names": ["devnets", "production"]}
        )), patch.object(routing, "run_command", return_value=reply) as command:
            rc, result = routing.build_result(target, 3)
        return rc, result, command

    def test_active_hosted_id_routes_with_generic_datasources(self):
        rc, result, command = self.route("focil-devnet-1")
        self.assertEqual(rc, 0)
        self.assertEqual(result["classification"], "remote-panda")
        self.assertEqual(result["remoteMatch"], "focil-devnet-1")
        self.assertEqual(result["remoteMatchKind"], "network")
        self.assertIn("network=focil-devnet-1", routing.render_text(rc, result))
        command.assert_called_once_with(["panda", "devnets", "-o", "json"], 3)

    def test_short_display_name_and_substrings_are_not_network_ids(self):
        for target in ["devnet-1", "focil", "focil-devnet-10", "production-extra"]:
            with self.subTest(target=target):
                rc, result, _ = self.route(target)
                self.assertEqual(rc, 3)
                self.assertEqual(result["status"], "target-not-found")

    def test_inactive_network_is_not_ready(self):
        rc, result, _ = self.route("focil-devnet-1", networks=[
            {"id": "focil-devnet-1", "status": "inactive"}
        ])
        self.assertEqual(rc, 3)
        self.assertIsNone(result["classification"])

    def test_valid_empty_inventory_is_absence(self):
        rc, result, _ = self.route("focil-devnet-1", networks=[])
        self.assertEqual(rc, 3)
        self.assertEqual(result["devnets"]["state"], "ready")

    def test_discovery_errors_are_not_absence(self):
        for reply in [(1, "", "permission denied"), (124, "", "timed out"),
                      (None, "", "command not found"), (0, "not JSON", "")]:
            with self.subTest(reply=reply):
                rc, result, _ = self.route("focil-devnet-1", reply=reply)
                self.assertEqual(rc, 2)
                self.assertEqual(result["status"], "devnet-inventory-unavailable")
                self.assertIn("PANDA_DEVNET_INVENTORY_UNAVAILABLE",
                              routing.render_text(rc, result))

    def test_invalid_inventory_cannot_claim_absence_or_ready(self):
        for payload in [None, [], {}, {"networks": None}, {"networks": {}},
                        {"networks": ["focil-devnet-1"]},
                        {"networks": [{"id": "focil-devnet-1"}]},
                        {"networks": [{"id": "", "status": "active"}]}]:
            with self.subTest(payload=payload):
                rc, result, _ = self.route("focil-devnet-1", reply=(0, json.dumps(payload), ""))
                self.assertEqual(rc, 2)
                self.assertEqual(result["devnets"]["state"], "invalid_shape")

    def test_unavailable_datasources_block_remote_without_inventory_probe(self):
        rc, result, command = self.route("focil-devnet-1", panda={
            "state": "unavailable", "names": [], "error": "datasources=null"
        })
        self.assertEqual(rc, 2)
        self.assertEqual(result["status"], "panda-unavailable")
        command.assert_not_called()

    def test_exact_datasource_compatibility_needs_no_inventory(self):
        rc, result, command = self.route("production")
        self.assertEqual(rc, 0)
        self.assertIn("datasource=production", routing.render_text(rc, result))
        command.assert_not_called()

    def test_local_precedence_survives_unavailable_remote_discovery(self):
        rc, result, command = self.route("local-test", local={
            "state": "ready", "names": ["local-test"]
        }, panda={"state": "unavailable", "names": [], "error": "not ready"})
        self.assertEqual(rc, 0)
        self.assertEqual(result["classification"], "local-kurtosis")
        command.assert_not_called()

    def test_no_target_keeps_generic_readiness_without_inventory(self):
        rc, result, command = self.route(None)
        self.assertEqual(rc, 0)
        self.assertIn("panda_datasources=2", routing.render_text(rc, result))
        command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
