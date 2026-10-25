"""Unit Tests for cramt/m365-copilot-proxy Integration & Markdown-Fence Tool Emulation."""

from __future__ import annotations

import json
import unittest

from machybrid.m365_proxy import (
    M365CopilotProxyManager,
    M365ModelCatalog,
    M365ProxySettings,
    M365ToolEmulator,
)


class TestM365ProxyIntegration(unittest.TestCase):
    def test_resolves_unsafe_magic_model_to_gpt_5_5_think_deeper(self) -> None:
        self.assertEqual(
            M365ModelCatalog.resolve_model(None),
            "gpt-5.5-think-deeper",
        )
        self.assertEqual(
            M365ModelCatalog.resolve_model("m365-copilot"),
            "gpt-5.5-think-deeper",
        )
        self.assertEqual(
            M365ModelCatalog.resolve_model("gpt-6.1-sol"),
            "gpt-6.1-sol",
        )

    def test_formats_tools_into_markdown_fence_block_with_shell_routing(self) -> None:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write content to a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "edit_file",
                    "description": "Replace old text with new text",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "old": {"type": "string"},
                            "new": {"type": "string"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "run_command",
                    "description": "Run shell command",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "CommandLine": {"type": "string"},
                        },
                    },
                },
            },
        ]
        prompt_block = M365ToolEmulator.format_tools_prompt(tools)
        self.assertIn("<tools>", prompt_block)
        self.assertIn("```write_file", prompt_block)
        self.assertIn("<<<<<<< SEARCH", prompt_block)
        self.assertIn("```bash block", prompt_block)
        self.assertIn("run_command", prompt_block)

    def test_parses_fenced_tool_calls_and_shell_routing(self) -> None:
        tools = [
            {
                "function": {
                    "name": "edit_file",
                    "parameters": {
                        "properties": {
                            "path": {"type": "string"},
                            "old": {"type": "string"},
                            "new": {"type": "string"},
                        }
                    },
                }
            },
            {
                "function": {
                    "name": "run_command",
                    "parameters": {
                        "properties": {
                            "CommandLine": {"type": "string"},
                        }
                    },
                }
            },
        ]

        model_response = (
            "I will update `src/app.py` and run the test suite:\n"
            "```edit_file\n"
            "path: src/app.py\n"
            "<<<<<<< SEARCH\n"
            "DEBUG = True\n"
            "=======\n"
            "DEBUG = False\n"
            ">>>>>>> REPLACE\n"
            "```\n\n"
            "```bash\n"
            "pytest -v\n"
            "```\n"
        )

        calls = M365ToolEmulator.parse_fenced_tool_calls(model_response, declared_tools=tools)
        self.assertEqual(len(calls), 2)

        first = calls[0]
        self.assertEqual(first["function"]["name"], "edit_file")
        first_args = json.loads(first["function"]["arguments"])
        self.assertEqual(first_args["path"], "src/app.py")
        self.assertEqual(first_args["old"], "DEBUG = True")
        self.assertEqual(first_args["new"], "DEBUG = False")

        second = calls[1]
        self.assertEqual(second["function"]["name"], "run_command")
        second_args = json.loads(second["function"]["arguments"])
        self.assertEqual(second_args["CommandLine"], "pytest -v")

    def test_proxy_manager_environment_and_client_config(self) -> None:
        mgr = M365CopilotProxyManager(
            M365ProxySettings(
                port=4143,
                enable_interactive_approval=True,
                avoid_throttling=True,
                save_history=False,
            )
        )
        env = mgr.build_environment()
        self.assertEqual(env.get("M365_ENABLE_INTERACTIVE_APPROVAL"), "1")
        self.assertEqual(env.get("M365_AVOID_THROTTLING"), "1")
        self.assertNotIn("M365_SAVE_HISTORY", env)

        cfg = mgr.generate_client_config()
        self.assertEqual(
            cfg["providers"]["m365"]["baseUrl"],
            "http://127.0.0.1:4143/v1",
        )


if __name__ == "__main__":
    unittest.main()
