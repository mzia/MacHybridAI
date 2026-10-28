"""Unit, Integration & Security Tests for HybridOrchestrator and Loopback Server."""

from __future__ import annotations

import unittest

from machybrid.guardian import GuardianPolicy
from machybrid.orchestrator import ComputeMode, HybridConfig, HybridOrchestrator
from machybrid.providers import normalize_gemini_model
from machybrid.server import create_server, dispatch_request


class TestHybridOrchestratorAndServer(unittest.TestCase):
    def test_deprecated_gemini_models_automatically_upgrade(self) -> None:
        self.assertEqual(normalize_gemini_model("gemini-2.5-flash"), "gemini-3.8-flash")
        self.assertEqual(normalize_gemini_model("gemini-2.0-flash"), "gemini-3.8-flash")
        self.assertEqual(normalize_gemini_model("gemini-1.5-pro"), "gemini-3.8-flash")
        self.assertEqual(normalize_gemini_model("gemini-3.1-pro-preview"), "gemini-3.1-pro-preview")

    def test_fully_local_mode_never_calls_cloud(self) -> None:
        orchestrator = HybridOrchestrator(
            HybridConfig(compute_mode=ComputeMode.LOCAL)
        )
        res = orchestrator.run_task(
            prompt="Review portfolio holdings for Sam Reyes (sam.reyes@meridian.io).",
            mode=ComputeMode.LOCAL,
        )
        self.assertIsNone(res.cloud_Prompt_sent)
        self.assertTrue(res.receipt.nothing_left_mac)
        self.assertEqual(res.receipt.cloud_models_used, "not used")
        self.assertEqual(len(res.stations), 3)
        self.assertEqual(res.stations[0].station_id, "this_mac")

    def test_hybrid_mode_masks_pii_before_cloud_and_restores_in_result(self) -> None:
        orchestrator = HybridOrchestrator(
            HybridConfig(
                compute_mode=ComputeMode.HYBRID,
                cloud_provider="gemini",
                guardian_policy=GuardianPolicy.REVERSIBLE_MASK,
            )
        )
        raw_prompt = (
            "Benchmark the Meridian deal for Sam Reyes (sam.reyes@meridian.io, "
            "415-555-0199) against comparable SaaS buyouts."
        )
        res = orchestrator.run_task(prompt=raw_prompt, mode=ComputeMode.HYBRID)

        # Verify PII never appeared in the prompt sent to cloud
        self.assertIsNotNone(res.cloud_Prompt_sent)
        assert res.cloud_Prompt_sent is not None
        self.assertNotIn("Sam Reyes", res.cloud_Prompt_sent)
        self.assertNotIn("sam.reyes@meridian.io", res.cloud_Prompt_sent)
        self.assertNotIn("415-555-0199", res.cloud_Prompt_sent)
        self.assertIn("[PERSON_1]", res.cloud_Prompt_sent)
        self.assertIn("[EMAIL_1]", res.cloud_Prompt_sent)
        self.assertIn("[PHONE_1]", res.cloud_Prompt_sent)

        # Verify real values were restored locally in final_output
        self.assertIn("Sam Reyes", res.final_output)
        self.assertIn("sam.reyes@meridian.io", res.final_output)
        self.assertGreaterEqual(res.receipt.pii_flagged_count, 3)
        self.assertGreaterEqual(res.receipt.pii_restored_count, 1)
        self.assertEqual(len(res.stations), 4)

    def test_supports_antigravity_m365_and_openai_extension_providers(self) -> None:
        orchestrator = HybridOrchestrator()
        for provider in ("antigravity", "m365_copilot", "openai_compatible"):
            res = orchestrator.run_task(
                prompt="Analyze Q3 revenue multiples for Contact: Jane Doe (jane@acme.org).",
                mode=ComputeMode.HYBRID,
                cloud_provider=provider,
            )
            assert res.cloud_Prompt_sent is not None
            self.assertNotIn("jane@acme.org", res.cloud_Prompt_sent)
            self.assertIn("jane@acme.org", res.final_output)

    def test_loopback_server_rejects_non_localhost_binding(self) -> None:
        with self.assertRaises(ValueError):
            create_server(host="0.0.0.0", port=0)

    def test_loopback_server_endpoints_end_to_end(self) -> None:
        orchestrator = HybridOrchestrator()

        # 1. GET /health
        status, health = dispatch_request(orchestrator, "GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(health["status"], "ok")

        # 2. POST /v1/guardian/inspect
        status, inspected = dispatch_request(
            orchestrator,
            "POST",
            "/v1/guardian/inspect",
            {"text": "Client: Alex Rivera, email alex.rivera@corp.com"},
        )
        self.assertEqual(status, 200)
        self.assertTrue(inspected["pii_flagged"])
        self.assertNotIn("alex.rivera@corp.com", inspected["sanitized_text"])
        self.assertIn("alex.rivera@corp.com", inspected["restored_preview"])

        # 3. POST /v1/tasks/run
        status, task_res = dispatch_request(
            orchestrator,
            "POST",
            "/v1/tasks/run",
            {
                "prompt": "Update deal deck for Client: Alex Rivera (alex.rivera@corp.com)",
                "mode": "hybrid",
                "cloud_provider": "gemini",
            },
        )
        self.assertEqual(status, 200)
        self.assertNotIn("alex.rivera@corp.com", task_res["cloud_prompt_sent"])
        self.assertIn("alex.rivera@corp.com", task_res["final_output"])

        # 4. POST /v1/m365/control (emulate_tools)
        status, m365_res = dispatch_request(
            orchestrator,
            "POST",
            "/v1/m365/control",
            {
                "action": "emulate_tools",
                "tools": [
                    {
                        "function": {
                            "name": "run_command",
                            "parameters": {"properties": {"CommandLine": {"type": "string"}}},
                        }
                    }
                ],
                "model_output": "```bash\nls -la\n```",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(m365_res["parsed_tool_calls"]), 1)
        self.assertEqual(
            m365_res["parsed_tool_calls"][0]["function"]["name"],
            "run_command",
        )


class TestRealTelemetry(unittest.TestCase):
    def test_collect_telemetry_returns_valid_ranges(self) -> None:
        """collect_telemetry() must always return in-range values regardless of platform."""
        from machybrid.orchestrator import HybridOrchestrator

        t = HybridOrchestrator.collect_telemetry(tokens=42)
        self.assertGreaterEqual(t.cpu_percent, 0)
        self.assertLessEqual(t.cpu_percent, 100)
        self.assertGreaterEqual(t.memory_percent, 0)
        self.assertLessEqual(t.memory_percent, 100)
        self.assertGreaterEqual(t.gpu_percent, 0)
        self.assertLessEqual(t.gpu_percent, 100)
        self.assertGreaterEqual(t.unified_memory_gb, 8)
        self.assertEqual(t.tokens_processed, 42)

    def test_cpu_helper_returns_int_in_range(self) -> None:
        from machybrid.orchestrator import HybridOrchestrator

        val = HybridOrchestrator._read_cpu_percent_darwin()
        self.assertIsInstance(val, int)
        self.assertGreaterEqual(val, 0)
        self.assertLessEqual(val, 100)

    def test_memory_helper_returns_int_in_range(self) -> None:
        from machybrid.orchestrator import HybridOrchestrator

        val = HybridOrchestrator._read_memory_percent_darwin()
        self.assertIsInstance(val, int)
        self.assertGreaterEqual(val, 0)
        self.assertLessEqual(val, 100)


if __name__ == "__main__":
    unittest.main()
