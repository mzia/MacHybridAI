"""Hybrid Split-Compute Agentic Engine for the MacHybridAI CLI.

Brings an Antigravity-style autonomous coding & computer agent loop to the terminal,
powered by MacHybridAI's 4-Station Privacy Gate:
  1. Station 1 (This Mac): Workspace-jailed local tools (`list_files`, `read_file`,
     `search_code`, `rag_search`, `edit_file`, `write_file`, `run_command`).
  2. Station 2 (Privacy Gate): Every prompt, file excerpt, and tool output is scrubbed
     on-device by `PIIGuardian` before leaving the Mac for any cloud model.
  3. Station 3 (Cloud or Local Reasoning): Works with 100% local Apple Silicon MLX,
     Smart Auto routing, Multi-Cloud Consensus, or ANY cloud provider (OpenAI,
     Anthropic Claude, Google Gemini, OpenRouter, xAI Grok, Groq, DeepSeek,
     Mistral, Perplexity, Together, M365 Copilot, Azure/Custom).
  4. Station 4 (Local Restoration & Audit): Restores `PIIVault` tokens locally before
     writing edits to disk or printing answers, and emits a SHA-256 Privacy Receipt.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import shlex
import subprocess  # nosec B404
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .m365_proxy import M365ToolEmulator
from .orchestrator import ComputeMode, ExecutionReceipt, HybridOrchestrator
from .providers import LocalModelProvider, ProviderResponse

_IGNORED_DIRS = frozenset(
    {
        ".git",
        ".build",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        ".ruff_cache",
        ".pytest_cache",
        "dist",
        "build",
    }
)


@dataclass
class AgentToolCall:
    """Represents a single tool invocation executed during an agentic step."""

    tool_name: str
    arguments: Dict[str, Any]
    output: str
    approved: bool = True
    duration_ms: int = 0
    pii_scrubbed_before_cloud: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AgentTurnRecord:
    """Captures one reasoning + tool execution iteration of the hybrid agent."""

    step: int
    mode_used: str
    provider_used: str
    model_used: str
    assistant_text: str
    tool_calls: List[AgentToolCall] = field(default_factory=list)
    outbound_sanitized_sha256: str = ""
    pii_flagged_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "mode_used": self.mode_used,
            "provider_used": self.provider_used,
            "model_used": self.model_used,
            "assistant_text": self.assistant_text,
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "outbound_sanitized_sha256": self.outbound_sanitized_sha256,
            "pii_flagged_count": self.pii_flagged_count,
        }


@dataclass
class AgentRunResult:
    """Complete result of running a hybrid agentic CLI task."""

    goal: str
    workspace: str
    final_output: str
    steps: List[AgentTurnRecord]
    receipt: ExecutionReceipt
    plan_mode: bool = False
    total_tool_calls: int = 0
    total_duration_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "workspace": self.workspace,
            "final_output": self.final_output,
            "plan_mode": self.plan_mode,
            "total_tool_calls": self.total_tool_calls,
            "total_duration_ms": self.total_duration_ms,
            "steps": [s.to_dict() for s in self.steps],
            "receipt": asdict(self.receipt),
        }


class WorkspaceToolbox:
    """Workspace-jailed local tool runner for the Hybrid CLI Agent.

    Strictly enforces canonical path containment inside `workspace_root` to prevent
    path traversal (CWE-22) and requires approval for mutating actions (`write_file`,
    `edit_file`, `run_command`).
    """

    MUTATING_TOOLS = frozenset({"write_file", "edit_file", "run_command"})

    def __init__(
        self,
        workspace_root: str,
        plan_mode: bool = False,
        auto_approve: bool = False,
        approval_callback: Optional[Callable[[str, Dict[str, Any], str], bool]] = None,
    ) -> None:
        self.workspace_root = os.path.realpath(os.path.abspath(os.path.expanduser(workspace_root)))
        self.plan_mode = plan_mode
        self.auto_approve = auto_approve
        self.approval_callback = approval_callback

    @staticmethod
    def tool_schemas() -> List[Dict[str, Any]]:
        """OpenAI/Anthropic/M365-compatible JSON schemas for all local workspace tools."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "List files and directories inside the workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Relative directory path (default '.')"},
                            "max_depth": {"type": "integer", "description": "Maximum depth (1-4, default 2)"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read lines from a UTF-8 text file inside the workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Relative path to the file"},
                            "start_line": {"type": "integer", "description": "1-based start line (default 1)"},
                            "end_line": {"type": "integer", "description": "1-based end line (default 200)"},
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_code",
                    "description": "Search workspace source files for a text or regex pattern.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query or regex"},
                            "path": {"type": "string", "description": "Optional relative subdirectory"},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Create or overwrite a file inside the workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Relative file path"},
                            "content": {"type": "string", "description": "Full UTF-8 file content"},
                        },
                        "required": ["path", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "edit_file",
                    "description": "Replace an exact text block in a workspace file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Relative file path"},
                            "old": {"type": "string", "description": "Exact existing text to replace"},
                            "new": {"type": "string", "description": "Replacement text"},
                        },
                        "required": ["path", "old", "new"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "run_command",
                    "description": "Execute a non-shell command (e.g. git status, pytest, swift test) inside the workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string", "description": "Command and arguments to run"},
                        },
                        "required": ["command"],
                    },
                },
            },
        ]

    def resolve_safe_path(self, rel_path: str) -> Path:
        """Resolves `rel_path` strictly inside `workspace_root`, rejecting traversal or symlink escapes."""
        cleaned = (rel_path or ".").strip()
        if "\x00" in cleaned:
            raise ValueError("Invalid null byte in path")
        if os.path.isabs(cleaned):
            candidate = os.path.realpath(cleaned)
        else:
            candidate = os.path.realpath(os.path.join(self.workspace_root, cleaned))
        if os.path.commonpath([self.workspace_root, candidate]) != self.workspace_root:
            raise ValueError(f"Security policy: path '{rel_path}' escapes workspace root.")
        return Path(candidate)

    def _request_approval(self, tool_name: str, args: Dict[str, Any], preview: str) -> bool:
        if self.plan_mode:
            return False
        if self.auto_approve:
            return True
        if self.approval_callback is not None:
            return bool(self.approval_callback(tool_name, args, preview))
        return False

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Tuple[str, bool]:
        """Executes a workspace tool safely and returns `(output_text, was_approved)`."""
        name = tool_name.strip().lower()
        if name in {"bash", "shell", "run", "sh", "zsh"}:
            name = "run_command"

        if name == "list_files":
            return self._tool_list_files(arguments), True
        if name == "read_file":
            return self._tool_read_file(arguments), True
        if name == "search_code":
            return self._tool_search_code(arguments), True
        if name == "write_file":
            return self._tool_write_file(arguments)
        if name == "edit_file":
            return self._tool_edit_file(arguments)
        if name == "run_command":
            return self._tool_run_command(arguments)
        return f"[Unknown tool: {tool_name}]", False

    def _tool_list_files(self, args: Dict[str, Any]) -> str:
        rel = str(args.get("path", "."))
        max_depth = max(1, min(4, int(args.get("max_depth", 2))))
        try:
            target = self.resolve_safe_path(rel)
            if not target.exists():
                return f"Path not found: {rel}"
            if target.is_file():
                return str(target.relative_to(self.workspace_root))
            entries: List[str] = []
            base_depth = len(target.parts)
            for root, dirs, files in os.walk(target):
                dirs[:] = sorted(d for d in dirs if d not in _IGNORED_DIRS)
                cur_depth = len(Path(root).parts) - base_depth
                if cur_depth >= max_depth:
                    dirs.clear()
                rel_root = os.path.relpath(root, self.workspace_root)
                for fname in sorted(files):
                    if fname.startswith(".DS_Store"):
                        continue
                    rel_file = fname if rel_root == "." else os.path.join(rel_root, fname)
                    entries.append(rel_file)
                    if len(entries) >= 200:
                        entries.append("... (truncated at 200 files)")
                        return "\n".join(entries)
            return "\n".join(entries) if entries else "(empty directory)"
        except Exception as exc:
            return f"list_files error: {exc}"

    def _tool_read_file(self, args: Dict[str, Any]) -> str:
        rel = str(args.get("path", "")).strip()
        if not rel:
            return "read_file error: 'path' is required"
        start_line = max(1, int(args.get("start_line", 1)))
        end_line = max(start_line, min(start_line + 250, int(args.get("end_line", start_line + 199))))
        try:
            target = self.resolve_safe_path(rel)
            if not target.is_file():
                return f"File not found: {rel}"
            lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
            selected = lines[start_line - 1 : end_line]
            numbered = [f"{idx}: {line}" for idx, line in enumerate(selected, start=start_line)]
            header = f"[{rel} lines {start_line}-{min(end_line, len(lines))} of {len(lines)}]"
            return header + "\n" + "\n".join(numbered)
        except Exception as exc:
            return f"read_file error: {exc}"

    def _tool_search_code(self, args: Dict[str, Any]) -> str:
        query = str(args.get("query", "")).strip()
        if not query:
            return "search_code error: 'query' is required"
        rel = str(args.get("path", "."))
        try:
            target = self.resolve_safe_path(rel)
            try:
                pattern = re.compile(query, re.IGNORECASE)
            except re.error:
                pattern = re.compile(re.escape(query), re.IGNORECASE)
            hits: List[str] = []
            for root, dirs, files in os.walk(target):
                dirs[:] = sorted(d for d in dirs if d not in _IGNORED_DIRS)
                for fname in sorted(files):
                    fpath = Path(root) / fname
                    try:
                        if fpath.stat().st_size > 512_000:
                            continue
                        text = fpath.read_text(encoding="utf-8", errors="ignore")
                    except OSError:
                        continue
                    rel_file = os.path.relpath(fpath, self.workspace_root)
                    for lineno, line in enumerate(text.splitlines(), start=1):
                        if pattern.search(line):
                            hits.append(f"{rel_file}:{lineno}: {line.strip()[:160]}")
                            if len(hits) >= 40:
                                hits.append("... (truncated at 40 matches)")
                                return "\n".join(hits)
            return "\n".join(hits) if hits else f"No matches found for '{query}'."
        except Exception as exc:
            return f"search_code error: {exc}"

    def _tool_write_file(self, args: Dict[str, Any]) -> Tuple[str, bool]:
        rel = str(args.get("path", "")).strip()
        content = str(args.get("content", ""))
        if not rel:
            return "write_file error: 'path' is required", False
        try:
            target = self.resolve_safe_path(rel)
        except ValueError as exc:
            return str(exc), False

        preview = f"Write {len(content)} bytes to {rel}"
        if not self._request_approval("write_file", args, preview):
            reason = "Plan Mode (read-only)" if self.plan_mode else "denied by user"
            return f"[Blocked write_file on {rel}: {reason}]", False

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return f"Wrote {len(content)} characters to {rel}.", True
        except OSError as exc:
            return f"write_file error: {exc}", False

    def _tool_edit_file(self, args: Dict[str, Any]) -> Tuple[str, bool]:
        rel = str(args.get("path", "")).strip()
        old_text = str(args.get("old", ""))
        new_text = str(args.get("new", ""))
        if not rel or not old_text:
            return "edit_file error: 'path' and 'old' are required", False
        try:
            target = self.resolve_safe_path(rel)
            if not target.is_file():
                return f"File not found: {rel}", False
            original = target.read_text(encoding="utf-8")
            if old_text not in original:
                return f"edit_file error: target snippet not found in {rel}", False
            updated = original.replace(old_text, new_text, 1)
            diff_preview = "".join(
                difflib.unified_diff(
                    original.splitlines(keepends=True),
                    updated.splitlines(keepends=True),
                    fromfile=f"a/{rel}",
                    tofile=f"b/{rel}",
                    n=2,
                )
            )
            if not self._request_approval("edit_file", args, diff_preview[:1200]):
                reason = "Plan Mode (read-only)" if self.plan_mode else "denied by user"
                return f"[Blocked edit_file on {rel}: {reason}]", False
            target.write_text(updated, encoding="utf-8")
            return f"Applied edit to {rel}:\n{diff_preview[:800]}", True
        except Exception as exc:
            return f"edit_file error: {exc}", False

    def _tool_run_command(self, args: Dict[str, Any]) -> Tuple[str, bool]:
        command = str(args.get("command", "")).strip()
        if not command:
            return "run_command error: 'command' is required", False
        try:
            argv = shlex.split(command)
        except ValueError as exc:
            return f"run_command parse error: {exc}", False
        if not argv:
            return "run_command error: empty command", False

        preview = f"Execute in {self.workspace_root}: {' '.join(argv)}"
        if not self._request_approval("run_command", args, preview):
            reason = "Plan Mode (read-only)" if self.plan_mode else "denied by user"
            return f"[Blocked run_command '{command}': {reason}]", False

        try:
            completed = subprocess.run(  # nosec B603
                argv,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=30.0,
                check=False,
            )
            stdout = (completed.stdout or "").strip()
            stderr = (completed.stderr or "").strip()
            combined = f"exit_code={completed.returncode}"
            if stdout:
                combined += f"\nSTDOUT:\n{stdout[:4000]}"
            if stderr:
                combined += f"\nSTDERR:\n{stderr[:2000]}"
            return combined, True
        except Exception as exc:
            return f"run_command error: {exc}", False


class HybridCLIAgent:
    """Antigravity-style Autonomous CLI Agent with MacHybridAI 4-Station Privacy Gate."""

    AGENT_SYSTEM_PROMPT = (
        "You are MacHybridAI CLI Agent — a privacy-first hybrid coding and computer agent on macOS. "
        "You operate inside the user's local workspace using tools (`list_files`, `read_file`, "
        "`search_code`, `edit_file`, `write_file`, `run_command`). "
        "All sensitive data in prompts and tool outputs has been masked into stand-in tokens "
        "like `[PERSON_1]`, `[EMAIL_1]`, `[SECRET_1]` by the on-device Privacy Gate. "
        "Preserve those stand-in tokens verbatim in your reasoning, edits, and answers so the Mac "
        "can restore real values locally. When you need a tool, invoke it via native tool calling "
        "or a Markdown fenced block (```read_file, ```search_code, ```edit_file, ```write_file, ```run_command). "
        "When the task is complete, respond clearly in Markdown without extra tool blocks."
    )

    def __init__(
        self,
        orchestrator: HybridOrchestrator,
        workspace_root: str = ".",
        max_steps: int = 6,
        plan_mode: bool = False,
        auto_approve: bool = False,
        approve_cloud_dispatch: bool = False,
        approval_callback: Optional[Callable[[str, Dict[str, Any], str], bool]] = None,
        cloud_approval_callback: Optional[Callable[[str, int, List[str]], Optional[str]]] = None,
        event_callback: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.workspace_root = os.path.realpath(os.path.abspath(os.path.expanduser(workspace_root)))
        self.max_steps = max(1, min(12, max_steps))
        self.approve_cloud_dispatch = approve_cloud_dispatch
        self.cloud_approval_callback = cloud_approval_callback
        self.event_callback = event_callback
        self.toolbox = WorkspaceToolbox(
            workspace_root=self.workspace_root,
            plan_mode=plan_mode,
            auto_approve=auto_approve,
            approval_callback=approval_callback,
        )
        self._conversation_turns: List[str] = []

    def _emit(self, stage: str, message: str) -> None:
        if self.event_callback is not None:
            self.event_callback(stage, message)

    def reset_memory(self) -> None:
        self._conversation_turns.clear()
        self.orchestrator.guardian.vault.clear()

    def _gather_workspace_overview(self) -> str:
        files_listing, _ = self.toolbox.execute("list_files", {"path": ".", "max_depth": 2})
        return f"Workspace root: {os.path.basename(self.workspace_root)}\nFiles:\n{files_listing[:2000]}"

    def _call_reasoning_model(
        self,
        active_mode: ComputeMode,
        cloud_provider: str,
        prompt_text: str,
        tools: List[Dict[str, Any]],
        effective_local_model: str,
    ) -> Tuple[ProviderResponse, str, int, List[str], bool]:
        """Executes Station 2 (Privacy Gate) + Station 3 (Local or Cloud) for one agent turn.

        Returns `(response, outbound_sha256, pii_flagged_count, pii_categories, nothing_left_mac)`.
        """
        if active_mode == ComputeMode.LOCAL:
            self._emit("station1", f"Running 100% locally on Apple Silicon ({effective_local_model or 'auto'})")
            local_provider = LocalModelProvider(
                backend_type=self.orchestrator.config.local_backend,
                model=effective_local_model,
                base_url=self.orchestrator.config.local_base_url,
                litert_model_path=self.orchestrator.config.litert_model_path,
            )
            resp = local_provider.generate(
                prompt=prompt_text,
                system_instruction=self.AGENT_SYSTEM_PROMPT,
            )
            return resp, "local_only_no_outbound_payload", 0, [], True

        # Station 2: Scrub all PII & secrets on-device BEFORE cloud dispatch
        redaction = self.orchestrator.guardian.redact(prompt_text)
        outbound = redaction.sanitized_text

        if redaction.forced_local:
            self._emit(
                "station2",
                f"Privacy Gate blocked cloud ({redaction.pii_count} sensitive item(s)) — forcing local execution",
            )
            local_provider = LocalModelProvider(
                backend_type=self.orchestrator.config.local_backend,
                model=effective_local_model,
                base_url=self.orchestrator.config.local_base_url,
                litert_model_path=self.orchestrator.config.litert_model_path,
            )
            resp = local_provider.generate(
                prompt=prompt_text,
                system_instruction=self.AGENT_SYSTEM_PROMPT,
            )
            return (
                resp,
                "local_only_no_outbound_payload",
                redaction.pii_count,
                redaction.categories,
                True,
            )

        if self.approve_cloud_dispatch and self.cloud_approval_callback is not None:
            approved = self.cloud_approval_callback(
                outbound, redaction.pii_count, redaction.categories
            )
            if approved is None:
                # User chose to keep this step local
                self._emit("station2", "Cloud dispatch declined — executing step 100% locally")
                local_provider = LocalModelProvider(
                    backend_type=self.orchestrator.config.local_backend,
                    model=effective_local_model,
                    base_url=self.orchestrator.config.local_base_url,
                    litert_model_path=self.orchestrator.config.litert_model_path,
                )
                resp = local_provider.generate(
                    prompt=prompt_text,
                    system_instruction=self.AGENT_SYSTEM_PROMPT,
                )
                return (
                    resp,
                    "local_only_no_outbound_payload",
                    redaction.pii_count,
                    redaction.categories,
                    True,
                )
            outbound = approved

        self._emit(
            "station2",
            f"Privacy Gate scrubbed {redaction.pii_count} sensitive item(s) before calling {cloud_provider}",
        )
        outbound_sha = hashlib.sha256(outbound.encode("utf-8")).hexdigest()

        # Station 3: Stateless Cloud Reasoning (single provider or Multi-Cloud Consensus)
        if cloud_provider.lower().strip() == "consensus":
            res = self.orchestrator.run_task(
                prompt=prompt_text,
                mode=ComputeMode.HYBRID,
                cloud_provider="consensus",
                approved_sanitized_prompt=outbound,
                save_to_history=False,
            )
            resp = ProviderResponse(
                provider="Multi-Cloud Consensus Arena",
                model=res.receipt.cloud_models_used,
                output_text=res.final_output,
                locality="cloud",
                tokens_used=res.telemetry.tokens_processed,
            )
            return resp, outbound_sha, redaction.pii_count, redaction.categories, False

        self._emit("station3", f"Dispatching sanitized reasoning to {cloud_provider} (store=false)")
        resp = self.orchestrator._invoke_cloud_provider(
            provider_name=cloud_provider,
            sanitized_prompt=outbound,
            tools=tools,
        )
        return resp, outbound_sha, redaction.pii_count, redaction.categories, False

    @staticmethod
    def _extract_tool_calls(
        resp: ProviderResponse,
        declared_tools: List[Dict[str, Any]],
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """Extracts tool calls from native OpenAI/Anthropic `tool_calls` OR fenced Markdown tool blocks."""
        parsed: List[Tuple[str, Dict[str, Any]]] = []
        raw_calls = list(resp.tool_calls or [])
        if not raw_calls and resp.output_text:
            raw_calls = M365ToolEmulator.parse_fenced_tool_calls(
                resp.output_text,
                declared_tools=declared_tools,
            )

        for tc in raw_calls:
            fn = tc.get("function", tc) if isinstance(tc, dict) else {}
            name = str(fn.get("name", "")).strip()
            if not name:
                continue
            raw_args = fn.get("arguments", {})
            if isinstance(raw_args, str):
                try:
                    args_dict = json.loads(raw_args)
                    if not isinstance(args_dict, dict):
                        args_dict = {}
                except ValueError:
                    args_dict = {}
            elif isinstance(raw_args, dict):
                args_dict = raw_args
            else:
                args_dict = {}
            parsed.append((name, args_dict))
        return parsed

    def run(
        self,
        goal: str,
        mode: Optional[ComputeMode] = None,
        cloud_provider: Optional[str] = None,
        attached_files: Optional[List[str]] = None,
    ) -> AgentRunResult:
        """Executes the autonomous multi-step Hybrid Agent loop for `goal`."""
        t0 = time.monotonic()
        requested_mode = mode or self.orchestrator.config.compute_mode
        active_mode = (
            self.orchestrator._resolve_smart_auto_mode(goal)
            if requested_mode == ComputeMode.AUTO
            else requested_mode
        )
        active_provider = cloud_provider or self.orchestrator.config.cloud_provider

        effective_local_model, guardrail_active, guardrail_reason = (
            self.orchestrator._apply_thermal_memory_guard(self.orchestrator.config.local_model)
        )
        if guardrail_active:
            self._emit("guardrail", guardrail_reason)

        tools = WorkspaceToolbox.tool_schemas()
        workspace_overview = self._gather_workspace_overview()

        attached_snippets: List[str] = []
        for raw_path in attached_files or []:
            text, _ = self.toolbox.execute("read_file", {"path": raw_path, "start_line": 1, "end_line": 200})
            attached_snippets.append(text)

        scratchpad: List[str] = [workspace_overview]
        if self._conversation_turns:
            scratchpad.append("Prior conversation:\n" + "\n".join(self._conversation_turns[-4:]))
        if attached_snippets:
            combined_attached = "\n\n".join(attached_snippets)
            if len(combined_attached) > 1200:
                chunks = self.orchestrator.rag.retrieve(query=goal, top_k=4, inline_context=combined_attached)
                scratchpad.append(
                    "Relevant local file excerpts (On-Device BM25 RAG):\n"
                    + self.orchestrator.rag.format_retrieved_context(chunks)
                )
            else:
                scratchpad.append("Attached local files:\n" + combined_attached)
        scratchpad.append(f"User Goal:\n{goal}")

        steps: List[AgentTurnRecord] = []
        total_pii_flagged = 0
        total_pii_restored = 0
        all_categories: List[str] = []
        total_tool_calls = 0
        last_outbound_sha = "local_only_no_outbound_payload"
        nothing_left_mac = True
        last_cloud_used = "not used"
        last_local_model = effective_local_model or "apple-silicon-local"
        final_answer = ""

        for step_idx in range(1, self.max_steps + 1):
            turn_prompt = "\n\n".join(scratchpad)
            resp, outbound_sha, pii_count, pii_cats, stayed_local = self._call_reasoning_model(
                active_mode=active_mode,
                cloud_provider=active_provider,
                prompt_text=turn_prompt,
                tools=tools,
                effective_local_model=effective_local_model,
            )

            total_pii_flagged += pii_count
            for c in pii_cats:
                if c not in all_categories:
                    all_categories.append(c)
            if not stayed_local:
                nothing_left_mac = False
                last_outbound_sha = outbound_sha
                last_cloud_used = f"{resp.provider} ({resp.model})"
            else:
                last_local_model = resp.model

            # Station 4: Restore real local values from PIIVault before local tool writes or final output
            restored_text, restored_n = self.orchestrator.guardian.restore(resp.output_text)
            total_pii_restored += restored_n

            extracted_calls = self._extract_tool_calls(resp, tools)
            step_tool_records: List[AgentToolCall] = []

            if extracted_calls:
                for tool_name, raw_args in extracted_calls:
                    # Restore stand-in tokens in tool arguments locally before executing on this Mac
                    restored_args: Dict[str, Any] = {}
                    for k, v in raw_args.items():
                        if isinstance(v, str):
                            rv, rn = self.orchestrator.guardian.restore(v)
                            total_pii_restored += rn
                            restored_args[k] = rv
                        else:
                            restored_args[k] = v

                    self._emit("tool", f"Executing local tool `{tool_name}`")
                    t_tool = time.monotonic()
                    tool_out, was_approved = self.toolbox.execute(tool_name, restored_args)
                    tool_ms = max(1, int((time.monotonic() - t_tool) * 1000))
                    total_tool_calls += 1

                    # Scrub tool output before adding to scratchpad for next cloud turn
                    scrubbed_count = 0
                    if active_mode != ComputeMode.LOCAL:
                        tool_redaction = self.orchestrator.guardian.redact(tool_out)
                        scrubbed_count = tool_redaction.pii_count
                        total_pii_flagged += scrubbed_count
                        for c in tool_redaction.categories:
                            if c not in all_categories:
                                all_categories.append(c)
                        scratchpad_out = tool_redaction.sanitized_text
                    else:
                        scratchpad_out = tool_out

                    step_tool_records.append(
                        AgentToolCall(
                            tool_name=tool_name,
                            arguments=restored_args,
                            output=tool_out[:1200],
                            approved=was_approved,
                            duration_ms=tool_ms,
                            pii_scrubbed_before_cloud=scrubbed_count,
                        )
                    )
                    scratchpad.append(f"Tool `{tool_name}` result:\n{scratchpad_out[:3000]}")

                steps.append(
                    AgentTurnRecord(
                        step=step_idx,
                        mode_used=active_mode.value,
                        provider_used=resp.provider,
                        model_used=resp.model,
                        assistant_text=restored_text,
                        tool_calls=step_tool_records,
                        outbound_sanitized_sha256=outbound_sha,
                        pii_flagged_count=pii_count,
                    )
                )
                continue

            # No tool calls requested -> final synthesized answer
            final_answer = restored_text
            steps.append(
                AgentTurnRecord(
                    step=step_idx,
                    mode_used=active_mode.value,
                    provider_used=resp.provider,
                    model_used=resp.model,
                    assistant_text=restored_text,
                    tool_calls=[],
                    outbound_sanitized_sha256=outbound_sha,
                    pii_flagged_count=pii_count,
                )
            )
            break

        if not final_answer and steps:
            final_answer = steps[-1].assistant_text

        self._conversation_turns.append(f"USER: {goal}\nASSISTANT: {final_answer[:600]}")

        receipt = ExecutionReceipt(
            mode_executed=active_mode.value,
            local_model_used=f"{last_local_model} (on this Mac)",
            local_agent_location="on this Mac",
            cloud_models_used=last_cloud_used,
            pii_flagged_count=total_pii_flagged,
            pii_restored_count=total_pii_restored,
            pii_categories=all_categories,
            nothing_left_mac=nothing_left_mac,
            cloud_zero_retention=True,
            outbound_payload_sha256=last_outbound_sha,
        )

        total_ms = max(1, int((time.monotonic() - t0) * 1000))
        return AgentRunResult(
            goal=goal,
            workspace=self.workspace_root,
            final_output=final_answer,
            steps=steps,
            receipt=receipt,
            plan_mode=self.toolbox.plan_mode,
            total_tool_calls=total_tool_calls,
            total_duration_ms=total_ms,
        )
