"""Unit & Security Tests for PIIGuardian ("Privacy Gate") and PIIVault."""

from __future__ import annotations

import unittest

from machybrid.guardian import GuardianPolicy, PIIGuardian, PIIVault


class TestPIIGuardian(unittest.TestCase):
    def test_masks_email_phone_ssn_and_restores_reversibly(self) -> None:
        guardian = PIIGuardian(policy=GuardianPolicy.REVERSIBLE_MASK)
        raw_prompt = (
            "Please review deal notes for Sam Reyes at sam.reyes@meridian.io, "
            "phone (415) 555-2671, SSN 123-45-6789."
        )
        result = guardian.redact(raw_prompt)

        self.assertTrue(result.pii_flagged)
        self.assertGreaterEqual(result.pii_count, 4)
        self.assertNotIn("sam.reyes@meridian.io", result.sanitized_text)
        self.assertNotIn("(415) 555-2671", result.sanitized_text)
        self.assertNotIn("123-45-6789", result.sanitized_text)
        self.assertNotIn("Sam Reyes", result.sanitized_text)
        self.assertIn("[EMAIL_1]", result.sanitized_text)
        self.assertIn("[PHONE_1]", result.sanitized_text)
        self.assertIn("[SSN_1]", result.sanitized_text)
        self.assertIn("[PERSON_1]", result.sanitized_text)

        # Simulate cloud model referencing the stand-in tokens
        cloud_output = (
            "Updated IC deck for [PERSON_1] and scheduled delivery to [EMAIL_1] "
            "after verifying phone [PHONE_1]."
        )
        restored, count = guardian.restore(cloud_output)
        self.assertEqual(count, 3)
        self.assertIn("Sam Reyes", restored)
        self.assertIn("sam.reyes@meridian.io", restored)
        self.assertIn("(415) 555-2671", restored)

    def test_luhn_credit_card_validation(self) -> None:
        guardian = PIIGuardian()
        # Valid Visa test number (passes Luhn) vs invalid checksum
        valid_card = "4532-0151-1283-0366"
        invalid_card = "4532-0151-1283-0367"

        res_valid = guardian.redact(f"Charge card {valid_card} immediately.")
        self.assertTrue(res_valid.pii_flagged)
        self.assertIn("[CREDIT_CARD_1]", res_valid.sanitized_text)
        self.assertNotIn(valid_card, res_valid.sanitized_text)

        res_invalid = guardian.redact(f"Order reference {invalid_card} is non-PII.")
        self.assertFalse(res_invalid.pii_flagged)
        self.assertIn(invalid_card, res_invalid.sanitized_text)

    def test_detects_api_keys_and_secrets(self) -> None:
        guardian = PIIGuardian()
        fake_key = "sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz123456"
        result = guardian.redact(f"My secret token is {fake_key} in config.")
        self.assertTrue(result.pii_flagged)
        self.assertIn("SECRET", result.categories)
        self.assertNotIn(fake_key, result.sanitized_text)

    def test_strict_redaction_mode_does_not_restore(self) -> None:
        guardian = PIIGuardian(policy=GuardianPolicy.STRICT_REDACT)
        result = guardian.redact("Email alice@example.com for details.")
        self.assertIn("[REDACTED_EMAIL]", result.sanitized_text)
        restored, count = guardian.restore(f"Sent to {result.sanitized_text}")
        self.assertEqual(count, 0)
        self.assertNotIn("alice@example.com", restored)

    def test_force_local_on_pii_policy(self) -> None:
        guardian = PIIGuardian(policy=GuardianPolicy.FORCE_LOCAL_ON_PII)
        result = guardian.redact("Contact bob@enterprise.org")
        self.assertTrue(result.forced_local)
        self.assertTrue(result.pii_flagged)

    def test_custom_sensitive_terms(self) -> None:
        guardian = PIIGuardian(custom_sensitive_terms=["Project Meridian", "CodeName-Omega"])
        result = guardian.redact("Rework the Project Meridian LBO model under CodeName-Omega.")
        self.assertEqual(result.pii_count, 2)
        self.assertNotIn("Project Meridian", result.sanitized_text)
        self.assertNotIn("CodeName-Omega", result.sanitized_text)
        restored, count = guardian.restore(result.sanitized_text)
        self.assertEqual(count, 2)
        self.assertEqual(
            restored,
            "Rework the Project Meridian LBO model under CodeName-Omega.",
        )

    def test_public_dict_never_leaks_original_value_by_default(self) -> None:
        vault = PIIVault()
        guardian = PIIGuardian(vault=vault)
        res = guardian.redact("Secret email ceo@company.com")
        audit = res.to_dict(include_original=False)
        serialized = str(audit)
        self.assertNotIn("ceo@company.com", serialized)


if __name__ == "__main__":
    unittest.main()
