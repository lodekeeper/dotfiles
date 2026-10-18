"""Verify budget failures cannot be rendered as ready audit prerequisites."""
import argparse
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts/notes' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


domains = load('bootstrap_domains', 'check-autonomy-domain-preflights.py')
renderer = load('bootstrap_renderer', 'render-autonomy-domain-statuses.py')


class BootstrapIntegrationTests(unittest.TestCase):
    def test_all_domains_share_one_identical_budget_command(self):
        args = argparse.Namespace(require_devnet_grafana=False, expected_github_actor='lodekeeper', timeout_seconds=30)
        checks = domains.build_checks(args, ROOT)
        budget = [c for c in checks if c[1] == 'bootstrapContextBudget']
        self.assertEqual({c[0] for c in budget}, set(domains.VALID_DOMAINS))
        self.assertEqual(len({domains.command_cache_key(c[2], c[3], 30) for c in budget}), 1)
        self.assertEqual(len(checks), 32)

    def test_budget_missing_or_failed_blocks_each_domain_and_success_is_scoped(self):
        for domain, names in renderer.EXPECTED_CHECKS.items():
            with self.subTest(domain=domain):
                checks = [{'domain': domain, 'name': name, 'ok': True, 'stdout': {'ok': True}, 'warnings': []} for name in names]
                payload = {'selectedDomains': [domain], 'checks': checks}
                good = renderer.render_statuses(payload)[renderer.SECTION_BY_DOMAIN[domain]]
                self.assertIn('projection verified (not actual injected-context coverage)', good)
                budget = next(c for c in checks if c['name'] == 'bootstrapContextBudget')
                budget['ok'] = False
                failed = renderer.render_statuses(payload)[renderer.SECTION_BY_DOMAIN[domain]]
                self.assertTrue(failed.startswith('BLOCKER:'))
                self.assertIn('Do not raise config limits automatically', failed)
                checks.remove(budget)
                self.assertTrue(renderer.render_statuses(payload)[renderer.SECTION_BY_DOMAIN[domain]].startswith('BLOCKER:'))


if __name__ == '__main__':
    unittest.main()
