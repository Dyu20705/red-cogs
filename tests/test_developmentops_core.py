import importlib.util
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, relative):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


security = load_module("developmentops_security", "developmentops/security.py")
settings = load_module("developmentops_settings", "developmentops/settings.py")
dedupe = load_module("developmentops_dedupe", "developmentops/dedupe.py")


class GithubSignatureTests(unittest.TestCase):
    def test_valid_signature(self):
        import hashlib
        import hmac

        body = b'{"zen":"keep it logically awesome"}'
        secret = "change-me"
        signature = "sha256=" + hmac.new(
            secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()

        self.assertTrue(security.verify_github_signature(secret, body, signature))

    def test_rejects_bad_signature(self):
        self.assertFalse(
            security.verify_github_signature("secret", b"body", "sha256=" + "0" * 64)
        )

    def test_rejects_missing_and_malformed_values(self):
        self.assertFalse(security.verify_github_signature("", b"body", "sha256=" + "0" * 64))
        self.assertFalse(security.verify_github_signature("secret", b"body", None))
        self.assertFalse(security.verify_github_signature("secret", b"body", "sha1=abc"))
        self.assertFalse(security.verify_github_signature("secret", b"body", "sha256=nothex"))

    def test_body_change_invalidates_signature(self):
        import hashlib
        import hmac

        signature = "sha256=" + hmac.new(b"secret", b"body", hashlib.sha256).hexdigest()
        self.assertFalse(security.verify_github_signature("secret", b"changed", signature))


class SettingsTests(unittest.TestCase):
    def test_defaults(self):
        item = settings.DevelopmentOpsSettings.from_env({})
        self.assertEqual(item.host, "127.0.0.1")
        self.assertEqual(item.port, 8765)
        self.assertTrue(item.receiver_enabled)

    def test_invalid_port_disables_receiver(self):
        item = settings.DevelopmentOpsSettings.from_env({"DEVELOPMENTOPS_PORT": "abc"})
        self.assertFalse(item.receiver_enabled)
        self.assertEqual(item.port, 8765)
        self.assertTrue(item.warnings)

    def test_out_of_range_port_disables_receiver(self):
        item = settings.DevelopmentOpsSettings.from_env({"DEVELOPMENTOPS_PORT": "70000"})
        self.assertFalse(item.receiver_enabled)


class DeliveryDedupeTests(unittest.TestCase):
    def test_seen_with_ttl(self):
        cache = dedupe.DeliveryDedupe(ttl_seconds=10, max_size=10)
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.assertFalse(cache.seen("a", now=now))
        self.assertTrue(cache.seen("a", now=now + timedelta(seconds=5)))
        self.assertFalse(cache.seen("a", now=now + timedelta(seconds=11)))

    def test_bounded_size(self):
        cache = dedupe.DeliveryDedupe(ttl_seconds=100, max_size=2)
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        cache.seen("a", now=now)
        cache.seen("b", now=now)
        cache.seen("c", now=now)
        self.assertEqual(len(cache), 2)
        self.assertFalse(cache.seen("a", now=now))

    def test_rejected_delivery_is_not_committed(self):
        cache = dedupe.DeliveryDedupe(ttl_seconds=100, max_size=10)
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.assertFalse(cache.contains("delivery-1", now=now))
        # A queue-full response must leave the delivery uncommitted so a retry is accepted.
        self.assertFalse(cache.contains("delivery-1", now=now + timedelta(seconds=1)))
        cache.remember("delivery-1", now=now + timedelta(seconds=2))
        self.assertTrue(cache.contains("delivery-1", now=now + timedelta(seconds=3)))

    def test_discard_allows_retry(self):
        cache = dedupe.DeliveryDedupe(ttl_seconds=100, max_size=10)
        cache.remember("delivery-2")
        self.assertTrue(cache.contains("delivery-2"))
        cache.discard("delivery-2")
        self.assertFalse(cache.contains("delivery-2"))


if __name__ == "__main__":
    unittest.main()
