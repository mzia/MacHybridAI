"""Unit & Security Tests for Local/iCloud Prompt History, Auto-Delete & Zero Cloud Retention."""

from __future__ import annotations

import tempfile
import unittest

from machybrid.history import (
    HistoryRetentionPolicy,
    HistoryStorageLocation,
    PromptHistoryManager,
)
from machybrid.orchestrator import ComputeMode, HybridOrchestrator
from machybrid.providers import GeminiProvider
from machybrid.server import dispatch_request


class TestPromptHistoryAndZeroCloudRetention(unittest.TestCase):
    def test_saves_prompt_history_locally_and_migrates_to_icloud(self) -> None:
        with tempfile.TemporaryDirectory() as local_dir, tempfile.TemporaryDirectory() as icloud_dir:
            mgr = PromptHistoryManager(
                storage_location=HistoryStorageLocation.LOCAL,
                retention_policy=HistoryRetentionPolicy.DAYS_30,
                custom_local_dir=local_dir,
                custom_icloud_dir=icloud_dir,
            )
            session = mgr.record_exchange(
                prompt="Draft Q4 memo for Client: Sam Reyes (sam.reyes@meridian.io)",
                response_text="Completed Q4 memo for Sam Reyes.",
                compute_mode="hybrid",
                cloud_provider="gemini",
                sanitized_cloud_prompt="Draft Q4 memo for Client: [PERSON_1] ([EMAIL_1])",
                pii_masked_count=2,
                pii_restored_count=2,
            )
            self.assertEqual(len(session.messages), 2)
            self.assertTrue((mgr.active_file_path).is_file())
            self.assertEqual(mgr.storage_location, HistoryStorageLocation.LOCAL)

            # Switch storage location to iCloud Drive and verify migration
            status = mgr.configure(
                storage_location=HistoryStorageLocation.ICLOUD,
                retention_policy=HistoryRetentionPolicy.DAYS_7,
                migrate_existing=True,
            )
            self.assertEqual(status["storage_location"], "icloud")
            self.assertEqual(status["retention_policy"], "7d")
            self.assertEqual(status["session_count"], 1)
            self.assertTrue(mgr.active_file_path.is_file())

    def test_auto_delete_periods_and_never_delete_option(self) -> None:
        with tempfile.TemporaryDirectory() as local_dir:
            mgr = PromptHistoryManager(
                storage_location=HistoryStorageLocation.LOCAL,
                retention_policy=HistoryRetentionPolicy.HOURS_24,
                custom_local_dir=local_dir,
            )
            # Record at t = 1000.0 (expires at 1000 + 86400 = 87400)
            mgr.record_exchange(
                prompt="Temporary 24h prompt",
                response_text="Response",
                compute_mode="local",
                cloud_provider="none",
                sanitized_cloud_prompt=None,
                pii_masked_count=0,
                pii_restored_count=0,
                now=1000.0,
            )
            # Before 24h: session is still present
            self.assertEqual(len(mgr.load_sessions(now=50_000.0)), 1)
            # After 24h (now = 90_000.0): auto-deleted!
            self.assertEqual(len(mgr.load_sessions(now=90_000.0)), 0)

            # Now configure NEVER delete policy
            mgr.configure(retention_policy=HistoryRetentionPolicy.NEVER)
            mgr.record_exchange(
                prompt="Permanent prompt that never auto-deletes",
                response_text="Permanent response",
                compute_mode="hybrid",
                cloud_provider="gemini",
                sanitized_cloud_prompt="Permanent prompt that never auto-deletes",
                pii_masked_count=0,
                pii_restored_count=0,
                now=1000.0,
            )
            # Even 10 years later, session is never auto-deleted
            ten_years_later = 1000.0 + (10 * 365 * 24 * 3600)
            sessions = mgr.load_sessions(now=ten_years_later)
            self.assertEqual(len(sessions), 1)
            self.assertIsNone(sessions[0].expires_at)

    def test_nothing_remains_in_cloud_ai_history(self) -> None:
        # Even if store=True is passed, GeminiProvider locks store=False
        provider = GeminiProvider(store=True)
        self.assertFalse(provider.store)
        resp = provider.generate("Test stateless cloud call")
        self.assertFalse(resp.metadata.get("store", True))
        self.assertTrue(resp.metadata.get("cloud_zero_retention"))

        with tempfile.TemporaryDirectory() as tmp_dir:
            mgr = PromptHistoryManager(custom_local_dir=tmp_dir)
            orchestrator = HybridOrchestrator(history_manager=mgr)
            res = orchestrator.run_task(
                prompt="Analyze SaaS churn for Contact: Sam Reyes (sam@meridian.io)",
                mode=ComputeMode.HYBRID,
            )
            self.assertTrue(res.receipt.cloud_zero_retention)
            self.assertIsNotNone(res.session_id)

            # Verify /v1/history endpoint via dispatch_request
            status, hist = dispatch_request(orchestrator, "GET", "/v1/history")
            self.assertEqual(status, 200)
            self.assertTrue(hist["cloud_ai_zero_retention"])
            self.assertEqual(hist["session_count"], 1)


if __name__ == "__main__":
    unittest.main()


class TestEncryptionKeyPersistence(unittest.TestCase):
    """Verify that the encryption key is persisted and reloaded correctly.

    The critical regression this guards against: encrypted history files must
    remain readable across process restarts.  If the key were ephemeral (a
    fresh os.urandom(32) on every __init__), the HMAC tag would never match
    on reload, silently returning an empty session list.
    """

    def test_key_is_reloaded_from_disk_across_instances(self) -> None:
        with tempfile.TemporaryDirectory() as local_dir:
            # First manager: writes encrypted file
            mgr1 = PromptHistoryManager(
                storage_location=HistoryStorageLocation.LOCAL,
                retention_policy=HistoryRetentionPolicy.NEVER,
                custom_local_dir=local_dir,
                encrypt_at_rest=True,
            )
            mgr1.record_exchange(
                prompt="Confidential memo",
                response_text="Reply",
                compute_mode="local",
                cloud_provider="none",
                sanitized_cloud_prompt=None,
                pii_masked_count=0,
                pii_restored_count=0,
            )
            self.assertTrue(mgr1.active_file_path.is_file())
            self.assertEqual(len(mgr1.load_sessions()), 1)

            # Confirm the key file was created
            key_path = mgr1._key_file_path
            self.assertTrue(key_path.is_file())
            self.assertEqual(len(key_path.read_bytes()), 32)

            # Second manager: same directory, should reload the same key
            mgr2 = PromptHistoryManager(
                storage_location=HistoryStorageLocation.LOCAL,
                retention_policy=HistoryRetentionPolicy.NEVER,
                custom_local_dir=local_dir,
                encrypt_at_rest=True,
            )
            sessions = mgr2.load_sessions()
            self.assertEqual(len(sessions), 1, "Encrypted session should be readable after key reload")
            self.assertEqual(sessions[0].messages[0].content, "Confidential memo")

    def test_explicit_key_bypasses_key_file(self) -> None:
        explicit = b"a" * 32
        with tempfile.TemporaryDirectory() as local_dir:
            mgr = PromptHistoryManager(
                storage_location=HistoryStorageLocation.LOCAL,
                retention_policy=HistoryRetentionPolicy.NEVER,
                custom_local_dir=local_dir,
                encrypt_at_rest=True,
                encryption_key=explicit,
            )
            self.assertEqual(mgr._encryption_key, explicit)
            # No key file should be written when an explicit key is supplied
            self.assertFalse(mgr._key_file_path.is_file())

    def test_unencrypted_manager_creates_no_key_file(self) -> None:
        with tempfile.TemporaryDirectory() as local_dir:
            mgr = PromptHistoryManager(
                storage_location=HistoryStorageLocation.LOCAL,
                retention_policy=HistoryRetentionPolicy.NEVER,
                custom_local_dir=local_dir,
                encrypt_at_rest=False,
            )
            mgr.record_exchange(
                prompt="Plain text record",
                response_text="Reply",
                compute_mode="local",
                cloud_provider="none",
                sanitized_cloud_prompt=None,
                pii_masked_count=0,
                pii_restored_count=0,
            )
            # Key file not touched when encryption is off
            self.assertFalse(mgr._key_file_path.is_file())
