"""Integration with cramt/m365-copilot-proxy for MacHybridAI.

Supports:
1. Managing the standalone `m365-proxy` process (`http://127.0.0.1:4141/v1`) and
   credentials config (`~/.config/opencode-m365/secrets.json` or interactive approval
   via `M365_ENABLE_INTERACTIVE_APPROVAL=1` and `M365_AVOID_THROTTLING=1`).
2. Complete model & M365 Tone catalog (`gpt-5.5-think-deeper` default for tool calling,
   `gpt-6-think-deeper`, `gpt-6.1-sol`, `gpt-6-sol`, `claude-sonnet-4.6`, etc.).
3. Prompt-emulated Markdown-fence & shell-routing tool calling protocol matching
   `https://github.com/cramt/m365-copilot-proxy`.
"""

from __future__ import annotations

import http.client
import json
import os
import shutil
import subprocess  # nosec B404
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class M365ModelInfo:
    """Metadata for an M365 Copilot Proxy model and its underlying SignalR tone."""

    id: str
    m365_tone: str
    name: str
    recommended_for_tools: bool
    requires_premium_seat: bool
    description: str


class M365ModelCatalog:
    """Canonical model catalog from cramt/m365-copilot-proxy."""

    DEFAULT_TOOL_MODEL = "gpt-5.5-think-deeper"

    MODELS: List[M365ModelInfo] = [
        M365ModelInfo(
            id="gpt-5.5-think-deeper",
            m365_tone="Gpt_5_5_Reasoning",
            name="M365 Copilot (GPT-5.5 Reasoning, Recommended Default)",
            recommended_for_tools=True,
            requires_premium_seat=False,
            description="Recommended default for agents/tool-calling (26/30 on bench, 100% tool harness compliance).",
        ),
        M365ModelInfo(
            id="gpt-6.1-sol",
            m365_tone="Gpt_61_Sol_Reasoning",
            name="M365 Copilot (GPT-6.1 Sol Reasoning)",
            recommended_for_tools=True,
            requires_premium_seat=False,
            description="Works on every Entra ID account; 40/40 on bench with relay_batch framing.",
        ),
        M365ModelInfo(
            id="gpt-6-sol",
            m365_tone="Gpt_6_Sol_Reasoning",
            name="M365 Copilot (GPT-6.0 Sol Reasoning)",
            recommended_for_tools=True,
            requires_premium_seat=False,
            description="Works on every work/school account; 40/40 with agent, 60/60 without.",
        ),
        M365ModelInfo(
            id="gpt-6-think-deeper",
            m365_tone="Gpt_6_Reasoning",
            name="M365 Copilot (GPT-6 Think Deeper)",
            recommended_for_tools=True,
            requires_premium_seat=True,
            description="GPT-6 reasoning with relay_batch framing (requires paid/premium Copilot seat).",
        ),
        M365ModelInfo(
            id="gpt-5.6-think-deeper",
            m365_tone="Gpt_5_6_Reasoning",
            name="M365 Copilot (GPT-5.6 Reasoning)",
            recommended_for_tools=True,
            requires_premium_seat=False,
            description="GPT-5.6 reasoning tone (27/30 on bench).",
        ),
        M365ModelInfo(
            id="claude-sonnet-4.6",
            m365_tone="Claude_Sonnet",
            name="M365 Copilot (Claude Sonnet 4.6)",
            recommended_for_tools=True,
            requires_premium_seat=False,
            description="Anthropic Claude Sonnet 4.6 via M365 (40/40 with relay_batch framing).",
        ),
        M365ModelInfo(
            id="claude-opus-4.8",
            m365_tone="Claude_Opus",
            name="M365 Copilot (Claude Opus 4.8)",
            recommended_for_tools=True,
            requires_premium_seat=True,
            description="Anthropic Claude Opus 4.8 on premium accounts (30/30 on bench).",
        ),
        M365ModelInfo(
            id="gpt-5.5",
            m365_tone="Gpt_5_5_Chat",
            name="M365 Copilot (GPT-5.5 Chat / Quick)",
            recommended_for_tools=False,
            requires_premium_seat=False,
            description="Strongest benchmarked fast chat tone (Gpt_5_5_Chat).",
        ),
    ]

    @classmethod
    def list_models(cls) -> List[Dict[str, Any]]:
        return [asdict(m) for m in cls.MODELS]

    @classmethod
    def resolve_model(cls, requested_model: Optional[str]) -> str:
        """Resolves empty or unsafe `m365-copilot` magic tone to `gpt-5.5-think-deeper`."""
        if not requested_model or requested_model in {"m365-copilot", "auto"}:
            return cls.DEFAULT_TOOL_MODEL
        return requested_model


class M365ToolEmulator:
    """Implements cramt/m365-copilot-proxy's Markdown-fence and shell-routing tool emulation.

    - Injects tool definitions inside a `<tools>` block as fenced Markdown templates.
    - When a shell tool (`bash`, `shell`, `run`, `run_command`) is present, adds
      shell-routing instructions so ```bash blocks route directly to the shell tool.
    - Parses fenced code blocks emitted by the model back into OpenAI-compatible
      `tool_calls` using a strictly linear O(N) line scanner (immune to ReDoS).
    """

    SHELL_TOOL_NAMES = {"bash", "shell", "run", "run_command", "sh", "zsh"}
    _ALLOWED_INFO_CHARS = frozenset(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-"
    )

    @classmethod
    def _extract_fenced_blocks(cls, text: str) -> List[Tuple[str, str]]:
        """Linear O(N) line parser for Markdown fenced blocks (` ```info ... ``` `)."""
        blocks: List[Tuple[str, str]] = []
        in_fence = False
        current_info = ""
        current_lines: List[str] = []

        for raw_line in text.splitlines():
            stripped = raw_line.strip()
            if not in_fence:
                if stripped.startswith("```"):
                    candidate_info = stripped[3:].strip()
                    if candidate_info and all(
                        ch in cls._ALLOWED_INFO_CHARS for ch in candidate_info
                    ):
                        in_fence = True
                        current_info = candidate_info
                        current_lines = []
            else:
                if stripped == "```":
                    blocks.append((current_info, "\n".join(current_lines)))
                    in_fence = False
                    current_info = ""
                    current_lines = []
                else:
                    current_lines.append(raw_line)

        return blocks

    @staticmethod
    def _extract_search_replace_diff(text: str) -> Optional[Tuple[str, str]]:
        """Linear O(N) line parser for `<<<<<<< SEARCH / ======= / >>>>>>> REPLACE` blocks."""
        lines = text.splitlines()
        state = "SEEK_SEARCH"
        old_lines: List[str] = []
        new_lines: List[str] = []

        for line in lines:
            stripped = line.strip()
            if state == "SEEK_SEARCH":
                if (
                    stripped.startswith("<<<<<")
                    and stripped.endswith("SEARCH")
                    and set(stripped[:-6].strip()) == {"<"}
                ):
                    state = "IN_OLD"
            elif state == "IN_OLD":
                if len(stripped) >= 5 and set(stripped) == {"="}:
                    state = "IN_NEW"
                else:
                    old_lines.append(line)
            elif state == "IN_NEW":
                if (
                    stripped.startswith(">>>>>")
                    and stripped.endswith("REPLACE")
                    and set(stripped[:-7].strip()) == {">"}
                ):
                    return "\n".join(old_lines), "\n".join(new_lines)
                new_lines.append(line)

        return None

    @classmethod
    def format_tools_prompt(cls, tools: List[Dict[str, Any]]) -> str:
        """Builds the `<tools>` Markdown-fence prompt block and shell-routing framing."""
        if not tools:
            return ""

        templates: List[str] = ["<tools>"]
        shell_tool_name: Optional[str] = None

        for tool in tools:
            fn = tool.get("function", tool)
            name = str(fn.get("name", "")).strip()
            if not name:
                continue
            if name.lower() in cls.SHELL_TOOL_NAMES and shell_tool_name is None:
                shell_tool_name = name

            desc = str(fn.get("description", "")).strip()
            params = fn.get("parameters", {}) or {}
            props: Dict[str, Any] = params.get("properties", {}) or {}

            scalar_lines: List[str] = []
            body_placeholder = ""
            has_old_new = "old" in props and "new" in props

            for prop_name, prop_schema in props.items():
                if has_old_new and prop_name in {"old", "new"}:
                    continue
                if prop_name in {"content", "body", "command", "code", "text"} and not body_placeholder:
                    body_placeholder = f"<{prop_name}>"
                else:
                    prop_type = prop_schema.get("type", "string")
                    scalar_lines.append(f"{prop_name}: <{prop_type}>")

            templates.append(f"# Tool: {name} — {desc}")
            templates.append(f"```{name}")
            templates.extend(scalar_lines)
            if has_old_new:
                templates.append("<<<<<<< SEARCH")
                templates.append("<old text>")
                templates.append("=======")
                templates.append("<new text>")
                templates.append(">>>>>>> REPLACE")
            elif body_placeholder:
                if scalar_lines:
                    templates.append("")
                templates.append(body_placeholder)
            templates.append("```")

        templates.append("</tools>")

        if shell_tool_name:
            templates.append(
                f"\nWhen executing commands or multi-step shell actions, do the whole step "
                f"by writing one ```bash block (it will automatically route to `{shell_tool_name}`)."
            )
        return "\n".join(templates)

    @classmethod
    def parse_fenced_tool_calls(
        cls,
        response_text: str,
        declared_tools: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Parses Markdown-fenced blocks into OpenAI-style `tool_calls`."""
        if not response_text:
            return []

        tool_map: Dict[str, Dict[str, Any]] = {}
        shell_target_name: Optional[str] = None
        for tool in declared_tools or []:
            fn = tool.get("function", tool)
            name = str(fn.get("name", "")).strip()
            if name:
                tool_map[name] = fn
                if name.lower() in cls.SHELL_TOOL_NAMES and shell_target_name is None:
                    shell_target_name = name

        tool_calls: List[Dict[str, Any]] = []

        for info_string, block_body in cls._extract_fenced_blocks(response_text):
            # Shell-routing: route ```bash / ```sh to the active shell tool if present
            target_tool: Optional[str] = None
            is_shell_routed = False
            if info_string in tool_map:
                target_tool = info_string
            elif info_string.lower() in {"bash", "sh", "zsh"} and (
                shell_target_name or not tool_map
            ):
                target_tool = shell_target_name or "bash"
                is_shell_routed = True

            if not target_tool:
                continue

            fn_schema = tool_map.get(target_tool, {})
            props = (fn_schema.get("parameters", {}) or {}).get("properties", {}) or {}

            if is_shell_routed:
                cmd_key = "command"
                for candidate_key in ("command", "CommandLine", "cmd", "script"):
                    if candidate_key in props:
                        cmd_key = candidate_key
                        break
                args_dict: Dict[str, Any] = {cmd_key: block_body.strip()}
            else:
                args_dict = cls._parse_fence_body(block_body, props)

            call_id = f"call_{uuid.uuid4().hex[:12]}"
            tool_calls.append(
                {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": target_tool,
                        "arguments": json.dumps(args_dict),
                    },
                }
            )

        return tool_calls

    @classmethod
    def _parse_fence_body(
        cls,
        block_body: str,
        props: Dict[str, Any],
    ) -> Dict[str, Any]:
        args: Dict[str, Any] = {}
        lines = block_body.splitlines()
        body_start_idx = 0

        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                body_start_idx = idx + 1
                break
            if stripped.startswith("<<<<<<<") and stripped.endswith("SEARCH"):
                body_start_idx = idx
                break
            key_part, sep, val_part = line.partition(":")
            key_clean = key_part.strip()
            val_clean = val_part.strip()
            if sep and key_clean.isidentifier() and val_clean and (not props or key_clean in props):
                args[key_clean] = cls._coerce_scalar(val_clean)
                body_start_idx = idx + 1
            else:
                body_start_idx = idx
                break

        remaining = "\n".join(lines[body_start_idx:]).strip()
        if not remaining:
            return args

        diff_pair = cls._extract_search_replace_diff(remaining)
        if diff_pair is not None:
            args["old"], args["new"] = diff_pair
            return args

        # Determine free-form body argument name
        body_arg_name = "content"
        for candidate in ("content", "body", "command", "code", "text"):
            if candidate in props and candidate not in args:
                body_arg_name = candidate
                break
        args[body_arg_name] = remaining
        return args

    @staticmethod
    def _coerce_scalar(raw_val: str) -> Any:
        if raw_val.lower() == "true":
            return True
        if raw_val.lower() == "false":
            return False
        if raw_val.lstrip("-").isdigit() and raw_val not in {"", "-"}:
            return int(raw_val)
        return raw_val


@dataclass
class M365ProxySettings:
    """Configuration for cramt/m365-copilot-proxy integration."""

    port: int = 4141
    host: str = "127.0.0.1"
    default_model: str = M365ModelCatalog.DEFAULT_TOOL_MODEL
    enable_interactive_approval: bool = True
    avoid_throttling: bool = True
    save_history: bool = False
    repo_dir: str = field(
        default_factory=lambda: os.path.expanduser("~/.local/share/m365-copilot-proxy")
    )
    secrets_path: str = field(
        default_factory=lambda: os.path.expanduser("~/.config/opencode-m365/secrets.json")
    )

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}/v1"


class M365CopilotProxyManager:
    """Manages lifecycle, configuration, and health of `m365-copilot-proxy`."""

    def __init__(self, settings: Optional[M365ProxySettings] = None) -> None:
        self.settings = settings or M365ProxySettings()
        self._process: Optional[subprocess.Popen[bytes]] = None

    def build_environment(self) -> Dict[str, str]:
        """Builds the environment variables for `m365-proxy`."""
        env = dict(os.environ)
        if self.settings.enable_interactive_approval:
            env["M365_ENABLE_INTERACTIVE_APPROVAL"] = "1"
        if self.settings.avoid_throttling:
            env["M365_AVOID_THROTTLING"] = "1"
            env["M365_DEBUG"] = "1"
        if self.settings.save_history:
            env["M365_SAVE_HISTORY"] = "1"
        return env

    def is_running(self) -> bool:
        """Checks if the local M365 Copilot Proxy is responding on `/v1/models`."""
        if self._process is not None and self._process.poll() is None:
            return True
        if self.settings.host not in {"127.0.0.1", "localhost"}:
            return False
        conn = http.client.HTTPConnection(self.settings.host, self.settings.port, timeout=1.2)
        try:
            conn.request("GET", "/v1/models")
            resp = conn.getresponse()
            return 200 <= resp.status < 300
        except OSError:
            return False
        finally:
            conn.close()

    def has_credentials_file(self) -> bool:
        """Checks whether an existing user-managed M365 configuration file is present."""
        target = Path(os.path.expanduser(self.settings.secrets_path))
        return target.is_file()

    def generate_client_config(self) -> Dict[str, Any]:
        """Generates the OpenAI-compatible provider config block for agents."""
        return {
            "providers": {
                "m365": {
                    "baseUrl": self.settings.base_url,
                    "api": "openai-completions",
                    "apiKey": "not-needed",
                    "compat": {
                        "supportsDeveloperRole": False,
                        "supportsReasoningEffort": False,
                        "supportsUsageInStreaming": False,
                    },
                    "models": [
                        {
                            "id": m.id,
                            "name": m.name,
                            "input": ["text", "image"],
                        }
                        for m in M365ModelCatalog.MODELS
                    ],
                }
            }
        }

    def start(self) -> Tuple[bool, str]:
        """Starts the `m365-proxy` process if installed on the system."""
        if self.is_running():
            return True, f"m365-copilot-proxy already active at {self.settings.base_url}"

        binary = shutil.which("m365-proxy")
        cmd: Optional[List[str]] = None
        cwd: Optional[str] = None

        if binary:
            cmd = [binary, str(self.settings.port)]
        elif os.path.isdir(self.settings.repo_dir) and shutil.which("pnpm"):
            cmd = ["pnpm", "run", "proxy", str(self.settings.port)]
            cwd = self.settings.repo_dir
        elif shutil.which("npx"):
            cmd = ["npx", "m365-proxy", str(self.settings.port)]

        if not cmd:
            return (
                False,
                "m365-proxy binary or Node/pnpm not found. Install https://github.com/cramt/m365-copilot-proxy.",
            )

        try:
            self._process = subprocess.Popen(
                cmd,
                cwd=cwd,
                env=self.build_environment(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True, f"Launched m365-copilot-proxy on port {self.settings.port}"
        except OSError as exc:
            return False, f"Failed to launch m365-copilot-proxy: {exc}"

    def stop(self) -> Tuple[bool, str]:
        """Stops the managed `m365-proxy` child process."""
        if self._process is None or self._process.poll() is not None:
            self._process = None
            return True, "m365-copilot-proxy is not running as a managed child process."
        self._process.terminate()
        try:
            self._process.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            self._process.kill()
        self._process = None
        return True, "Stopped managed m365-copilot-proxy process."

    def status_dict(self) -> Dict[str, Any]:
        return {
            "running": self.is_running(),
            "base_url": self.settings.base_url,
            "port": self.settings.port,
            "default_model": M365ModelCatalog.resolve_model(self.settings.default_model),
            "enable_interactive_approval": self.settings.enable_interactive_approval,
            "avoid_throttling": self.settings.avoid_throttling,
            "temporary_chat_mode": not self.settings.save_history,
            "secrets_configured": os.path.isfile(os.path.expanduser(self.settings.secrets_path)),
            "available_models": M365ModelCatalog.list_models(),
        }
