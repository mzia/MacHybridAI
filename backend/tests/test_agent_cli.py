"""Unit tests for the MacHybridAI Hybrid Agentic CLI (`machybrid` / `mh`)."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from machybrid.agent import HybridCLIAgent, WorkspaceToolbox
from machybrid.cli import _ANSI, handle_slash_command, main
from machybrid.orchestrator import ComputeMode, HybridOrchestrator
from machybrid.providers import ProviderResponse


class TestWorkspaceToolboxSecurityAndTools(unittest.TestCase):
    def test_workspace_sandbox_blocks_path_traversal_and_plan_mode_blocks_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sample_file = root / "app.py"
            sample_file.write_text("def greet():\n    return 'hello world'\n", encoding="utf-8")

            # 1. Plan mode allows reads & search, blocks mutating writes/edits/commands
            tb_plan = WorkspaceToolbox(str(root), plan_mode=True, auto_approve=True)
            listing, ok = tb_plan.execute("list_files", {"path": "."})
            self.assertTrue(ok)
            self.assertIn("app.py", listing)

            content, ok = tb_plan.execute("read_file", {"path": "app.py"})
            self.assertTrue(ok)
            self.assertIn("hello world", content)

            hits, ok = tb_plan.execute("search_code", {"query": "greet"})
            self.assertTrue(ok)
            self.assertIn("app.py:1:", hits)

            write_out, approved = tb_plan.execute("write_file", {"path": "new.txt", "content": "x"})
            self.assertFalse(approved)
            self.assertIn("Plan Mode", write_out)
            self.assertFalse((root / "new.txt").exists())

            cmd_out, approved = tb_plan.execute("run_command", {"command": "echo hi"})
            self.assertFalse(approved)
            self.assertIn("Plan Mode", cmd_out)

            # 2. Path traversal escape is rejected
            with self.assertRaises(ValueError):
                tb_plan.resolve_safe_path("../../etc/passwd")

            # 3. Auto-approve non-plan mode allows edit_file, write_file, and run_command
            tb_rw = WorkspaceToolbox(str(root), plan_mode=False, auto_approve=True)
            edit_out, edit_ok = tb_rw.execute(
                "edit_file",
                {"path": "app.py", "old": "hello world", "new": "hybrid agent"},
            )
            self.assertTrue(edit_ok)
            self.assertIn("hybrid agent", edit_out)
            self.assertIn("hybrid agent", sample_file.read_text(encoding="utf-8"))

            w_out, w_ok = tb_rw.execute("write_file", {"path": "sub/note.txt", "content": "saved"})
            self.assertTrue(w_ok)
            self.assertIn("Wrote 5", w_out)
            self.assertEqual((root / "sub" / "note.txt").read_text(encoding="utf-8"), "saved")

            rc_out, rc_ok = tb_rw.execute("run_command", {"command": "python3 -c 'print(42)'"})
            self.assertTrue(rc_ok)
            self.assertIn("exit_code=0", rc_out)
            self.assertIn("42", rc_out)


class TestHybridCLIAgentAndEndToEnd(unittest.TestCase):
    def test_multi_step_agent_scrubs_file_pii_before_cloud_and_restores_locally(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret_doc = root / "client.txt"
            secret_doc.write_text(
                "Client: Sam Reyes\nEmail: sam.reyes@meridian.io\nKey: sk-secret12345678901234567890\n",
                encoding="utf-8",
            )

            orchestrator = HybridOrchestrator()
            agent = HybridCLIAgent(
                orchestrator=orchestrator,
                workspace_root=str(root),
                max_steps=4,
                plan_mode=False,
                auto_approve=True,
            )

            observed_cloud_prompts = []

            def fake_cloud(provider_name: str, sanitized_prompt: str, tools=None) -> ProviderResponse:
                observed_cloud_prompts.append(sanitized_prompt)
                if len(observed_cloud_prompts) == 1:
                    # Step 1: Cloud asks to read `client.txt` via native tool_calls
                    return ProviderResponse(
                        provider=provider_name,
                        model="claude-sonnet-4-5",
                        output_text="Reading client.txt on-device...",
                        locality="cloud",
                        tool_calls=[
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "read_file",
                                    "arguments": json.dumps({"path": "client.txt"}),
                                },
                            }
                        ],
                    )
                # Step 2: Cloud uses stand-in tokens to write a summary file and reply
                return ProviderResponse(
                    provider=provider_name,
                    model="claude-sonnet-4-5",
                    output_text="Prepared executive brief for [PERSON_1] ([EMAIL_1]).",
                    locality="cloud",
                )

            with patch.object(orchestrator, "_invoke_cloud_provider", side_effect=fake_cloud):
                result = agent.run(
                    goal="Read client.txt and prepare a brief for Client: Sam Reyes (sam.reyes@meridian.io)",
                    mode=ComputeMode.HYBRID,
                    cloud_provider="anthropic",
                )

            # Verify 2 steps executed and 1 local tool call ran
            self.assertEqual(len(result.steps), 2)
            self.assertEqual(result.total_tool_calls, 1)

            # Verify ZERO raw PII/secrets ever reached the cloud prompt on EITHER turn!
            self.assertEqual(len(observed_cloud_prompts), 2)
            for sent in observed_cloud_prompts:
                self.assertNotIn("sam.reyes@meridian.io", sent)
                self.assertNotIn("sk-secret12345678901234567890", sent)
                self.assertNotIn("Sam Reyes", sent)

            # Verify Station 4 restored real local values in final output + emitted SHA-256 receipt
            self.assertIn("Sam Reyes", result.final_output)
            self.assertIn("sam.reyes@meridian.io", result.final_output)
            self.assertGreaterEqual(result.receipt.pii_flagged_count, 2)
            self.assertGreaterEqual(result.receipt.pii_restored_count, 2)
            self.assertEqual(len(result.receipt.outbound_payload_sha256), 64)
            self.assertEqual(len(result.receipt.receipt_signature_sha256), 64)

    def test_cli_subcommands_json_output_and_slash_commands(self) -> None:
        # 1. `machybrid providers --json`
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["--json", "providers"])
        self.assertEqual(rc, 0)
        prov_data = json.loads(buf.getvalue())
        ids = {p["id"] for p in prov_data["providers"]}
        self.assertIn("openai", ids)
        self.assertIn("anthropic", ids)
        self.assertIn("gemini", ids)

        # 2. `machybrid inspect --json`
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["--json", "inspect", "Contact: Sam Reyes (sam.reyes@meridian.io)"])
        self.assertEqual(rc, 0)
        insp = json.loads(buf.getvalue())
        self.assertTrue(insp["pii_flagged"])
        self.assertNotIn("sam.reyes@meridian.io", insp["sanitized_text"])
        self.assertIn("sam.reyes@meridian.io", insp["restored_preview"])

        # 3. `machybrid --mode local --json "Summarize workspace"` shorthand
        with tempfile.TemporaryDirectory() as tmp:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(["--mode", "local", "--workspace", tmp, "--json", "Summarize workspace"])
            self.assertEqual(rc, 0)
            run_data = json.loads(buf.getvalue())
            self.assertTrue(run_data["receipt"]["nothing_left_mac"])
            self.assertEqual(run_data["receipt"]["mode_executed"], "local")

        # 4. Interactive slash commands (/mode, /provider, /key, /plan, /approve, /yolo, /clear, /quit)
        orch = HybridOrchestrator()
        agent = HybridCLIAgent(orchestrator=orch, workspace_root=os.getcwd())
        ansi = _ANSI(False)
        box = [None]
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertTrue(handle_slash_command("/mode hybrid", agent, orch, ansi, box))
            self.assertEqual(orch.config.compute_mode, ComputeMode.HYBRID)
            self.assertTrue(handle_slash_command("/provider anthropic", agent, orch, ansi, box))
            self.assertEqual(orch.config.cloud_provider, "anthropic")
            self.assertTrue(handle_slash_command("/key anthropic sk-ant-ram-only", agent, orch, ansi, box))
            self.assertEqual(orch._runtime_api_keys.get("anthropic"), "sk-ant-ram-only")
            self.assertTrue(handle_slash_command("/plan", agent, orch, ansi, box))
            self.assertTrue(agent.toolbox.plan_mode)
            self.assertTrue(handle_slash_command("/approve", agent, orch, ansi, box))
            self.assertTrue(agent.approve_cloud_dispatch)
            self.assertTrue(handle_slash_command("/clear", agent, orch, ansi, box))
            self.assertFalse(handle_slash_command("/quit", agent, orch, ansi, box))


if __name__ == "__main__":
    unittest.main()
