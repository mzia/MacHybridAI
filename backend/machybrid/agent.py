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
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .m365_proxy import M365ToolEmulator
from .model_security import load_model_lockfile
from .orchestrator import ComputeMode, ExecutionReceipt, HybridOrchestrator
from .profiler import HardwareProfiler
from .providers import AppleFoundationModelsProvider, LocalModelProvider, ProviderResponse

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


def _is_ignored_dir(name: str) -> bool:
    return (
        name in _IGNORED_DIRS
        or name.endswith(".app")
        or name.endswith(".egg-info")
        or name.startswith(".aider.")
    )


def _is_ignored_file(name: str) -> bool:
    return name == ".DS_Store" or name.startswith(".aider.")


def diagnose_cli_permissions(
    workspace_root: str,
    orchestrator: Optional[HybridOrchestrator] = None,
) -> List[Dict[str, Any]]:
    """Checks all macOS filesystem, TCC, Metal/MLX, history, PATH, and cloud permissions needed by the CLI."""
    root = os.path.realpath(os.path.abspath(os.path.expanduser(workspace_root)))
    home = os.path.expanduser("~")
    checks: List[Dict[str, Any]] = []

    # 1. Workspace directory read & listing access (catches macOS TCC denials on Desktop/Documents/Downloads)
    try:
        with os.scandir(root) as it:
            entry_count = sum(1 for _ in it)
        checks.append(
            {
                "name": "workspace_read",
                "ok": True,
                "detail": f"Readable ({entry_count} top-level entries in {root})",
                "remediation": "",
            }
        )
    except PermissionError:
        checks.append(
            {
                "name": "workspace_read",
                "ok": False,
                "detail": f"macOS denied directory read access to {root}",
                "remediation": (
                    "Grant your terminal app access in macOS System Settings -> "
                    "Privacy & Security -> Files and Folders (or Full Disk Access)."
                ),
            }
        )
    except OSError as exc:
        checks.append(
            {
                "name": "workspace_read",
                "ok": False,
                "detail": f"Cannot read workspace {root}: {exc}",
                "remediation": "Verify the --workspace path exists and is accessible.",
            }
        )

    # 2. Workspace write permission (needed for edit_file / write_file)
    can_write = os.access(root, os.W_OK)
    checks.append(
        {
            "name": "workspace_write",
            "ok": can_write,
            "detail": f"{'Writable' if can_write else 'Read-only'} ({root})",
            "remediation": "" if can_write else "Use --plan for read-only mode or fix directory write permissions.",
        }
    )

    # 3. macOS TCC protected folder advisory
    protected_roots = [
        os.path.realpath(os.path.join(home, folder))
        for folder in ("Desktop", "Documents", "Downloads")
    ]
    in_tcc_folder = False
    for p in protected_roots:
        try:
            if os.path.commonpath([p, root]) == p:
                in_tcc_folder = True
                break
        except ValueError:
            continue
    checks.append(
        {
            "name": "macos_tcc_scope",
            "ok": True,
            "detail": (
                "Workspace is inside a macOS TCC-protected folder (Desktop/Documents/Downloads)"
                if in_tcc_folder
                else "Workspace is outside macOS TCC-protected Desktop/Documents/Downloads folders"
            ),
            "remediation": (
                "If macOS prompts, allow your terminal in System Settings -> Privacy & Security -> Files and Folders."
                if in_tcc_folder
                else ""
            ),
        }
    )

    # 4. Apple Silicon Metal & MLX local inference runtime
    mx_mod, mlx_lm_mod, mlx_err = HardwareProfiler.get_mlx_modules()
    mlx_ok = mx_mod is not None and mlx_lm_mod is not None
    if mlx_ok:
        mlx_detail = "Apple MLX + Metal GPU runtime available"
        mlx_fix = ""
    elif "metal" in mlx_err.lower():
        mlx_detail = f"Metal GPU unavailable in this session ({mlx_err.splitlines()[0][:140]})"
        mlx_fix = "Run in a standard macOS Terminal session with Metal GPU access (not a headless/sandboxed subshell)."
    else:
        mlx_detail = "MLX not installed in current Python interpreter"
        mlx_fix = "Install mlx-lm (`pip install mlx mlx-lm`) or run via Homebrew Python."
    checks.append(
        {
            "name": "mlx_metal_runtime",
            "ok": mlx_ok,
            "detail": mlx_detail,
            "remediation": mlx_fix,
        }
    )

    # 5. Local HuggingFace MLX model cache access
    hf_dir = Path(os.environ.get("HF_HUB_CACHE", os.path.expanduser("~/.cache/huggingface/hub")))
    try:
        if hf_dir.is_dir():
            cached = HardwareProfiler.scan_cached_models(hf_hub_dir=hf_dir)
            complete = [m for m in cached if m.is_complete]
            checks.append(
                {
                    "name": "hf_model_cache",
                    "ok": len(complete) > 0,
                    "detail": f"{len(complete)} complete local MLX model(s) cached in {hf_dir}",
                    "remediation": "" if complete else "Download a local model: huggingface-cli download mlx-community/gemma-3-4b-it-4bit",
                }
            )
        else:
            checks.append(
                {
                    "name": "hf_model_cache",
                    "ok": False,
                    "detail": f"HuggingFace cache folder not found ({hf_dir})",
                    "remediation": "Run: huggingface-cli download mlx-community/gemma-3-4b-it-4bit",
                }
            )
    except PermissionError:
        checks.append(
            {
                "name": "hf_model_cache",
                "ok": False,
                "detail": f"Permission denied reading {hf_dir}",
                "remediation": f"Allow read access to {hf_dir} or set HF_HUB_CACHE to a readable directory.",
            }
        )

    # 6. History storage directory permissions
    hist_dir = Path(os.path.expanduser("~/Library/Application Support/MacHybridAI/history"))
    try:
        probe = hist_dir
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        hist_writable = probe.is_dir() and os.access(probe, os.W_OK)
        checks.append(
            {
                "name": "history_storage",
                "ok": hist_writable,
                "detail": f"{'Accessible' if hist_writable else 'Not writable'} ({hist_dir})",
                "remediation": "" if hist_writable else "Ensure ~/Library/Application Support/MacHybridAI is writable.",
            }
        )
    except OSError:
        checks.append(
            {
                "name": "history_storage",
                "ok": False,
                "detail": f"Cannot stat {hist_dir} (sandboxed or restricted)",
                "remediation": "Run outside a restricted sandbox to persist local prompt history.",
            }
        )

    # 7. CLI installation & PATH check
    local_bin = os.path.expanduser("~/.local/bin")
    cli_bin = os.path.join(local_bin, "machybrid")
    on_path = local_bin in os.environ.get("PATH", "").split(os.pathsep)
    installed = os.path.isfile(cli_bin) and os.access(cli_bin, os.X_OK)
    checks.append(
        {
            "name": "cli_path_install",
            "ok": installed and on_path,
            "detail": f"installed={installed}, ~/.local/bin in PATH={on_path}",
            "remediation": "" if (installed and on_path) else "Run `./scripts/install_cli.sh` and add `export PATH=\"$HOME/.local/bin:$PATH\"` to ~/.zshrc.",
        }
    )

    # 8. Apple-signed OS Foundation Models availability (zero Hugging Face)
    orch = orchestrator or HybridOrchestrator()
    fm_ok, fm_reason = AppleFoundationModelsProvider.check_availability()
    checks.append(
        {
            "name": "apple_foundation_models",
            "ok": fm_ok,
            "detail": fm_reason if fm_reason else ("Apple-signed FoundationModels ready" if fm_ok else "Unavailable"),
            "remediation": (
                ""
                if fm_ok
                else "Requires macOS 26+ with Apple Intelligence enabled and a compiled MacHybridAI binary (`swift build -c release`)."
            ),
        }
    )

    # 9. Local model supply-chain protection posture
    sec = orch.get_model_security_settings()
    lock_entries = load_model_lockfile(Path(sec.lockfile_path) if sec.lockfile_path else None)
    if sec.allow_unverified_huggingface:
        sc_ok = False
        sc_detail = (
            f"BYPASS ENABLED (policy={sec.policy.value}) — unverified Hugging Face community repos allowed "
            f"(trust_remote_code=False & pickle/python files still blocked; {len(lock_entries)} pinned model(s))"
        )
        sc_fix = "Run `machybrid security revoke-hf` or switch to `--local-backend apple_fm` / `--local-model-dir <path>` to restore strict protection."
    else:
        sc_ok = True
        sc_detail = (
            f"Strict protection ACTIVE (policy={sec.policy.value}, trust_remote_code=False, "
            f"pickle/python blocked, {len(lock_entries)} SHA-256 pinned model(s))"
        )
        sc_fix = ""
    checks.append(
        {
            "name": "model_supply_chain",
            "ok": sc_ok,
            "detail": sc_detail,
            "remediation": sc_fix,
        }
    )

    # 10. Cloud AI provider readiness (reads presence metadata only, never secrets)
    ready_providers = [p["id"] for p in orch.list_cloud_providers() if p.get("configured")]
    checks.append(
        {
            "name": "cloud_providers_ready",
            "ok": len(ready_providers) > 0,
            "detail": (
                f"{len(ready_providers)} cloud provider(s) ready: {', '.join(ready_providers)}"
                if ready_providers
                else "0 cloud API keys set in environment (Local Apple Silicon & offline modes still work)"
            ),
            "remediation": "" if ready_providers else "Export GEMINI_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY — or use `/key <provider> <value>` in REPL.",
        }
    )
    return checks


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
    conversation_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "goal": self.goal,
            "workspace": self.workspace,
            "final_output": self.final_output,
            "plan_mode": self.plan_mode,
            "total_tool_calls": self.total_tool_calls,
            "total_duration_ms": self.total_duration_ms,
            "steps": [s.to_dict() for s in self.steps],
            "receipt": asdict(self.receipt),
        }


class CLISessionStore:
    """Local-only on-device CLI conversation store enabling `-c` and `--conversation=<uuid>` resume.

    All conversations stay strictly on this Mac (`~/Library/Application Support/MacHybridAI/cli_sessions`
    or `$MACHYBRID_SESSIONS_DIR`). Conversation IDs are strictly validated as canonical UUIDs and resolved
    against enumerated directory entries to prevent CWE-22 path injection.
    """

    def __init__(self, sessions_dir: Optional[Path] = None) -> None:
        raw_dir = (
            str(sessions_dir)
            if sessions_dir is not None
            else (
                os.environ.get("MACHYBRID_SESSIONS_DIR", "").strip()
                or os.path.expanduser("~/Library/Application Support/MacHybridAI/cli_sessions")
            )
        )
        self.sessions_dir = Path(os.path.realpath(os.path.abspath(os.path.expanduser(raw_dir))))

    @staticmethod
    def new_conversation_id() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def validate_conversation_id(raw_id: str) -> str:
        """Validates and normalizes a conversation UUID; raises ValueError on invalid input."""
        cleaned = (raw_id or "").strip()
        if not cleaned:
            raise ValueError("Conversation ID must not be empty.")
        try:
            parsed = uuid.UUID(cleaned)
        except ValueError as exc:
            raise ValueError(f"Invalid conversation ID '{cleaned}' (expected UUID format).") from exc
        return str(parsed)

    def _find_session_file(self, conversation_id: str) -> Optional[Path]:
        canonical = self.validate_conversation_id(conversation_id)
        try:
            if not self.sessions_dir.is_dir():
                return None
            for entry in self.sessions_dir.iterdir():
                if entry.is_file() and entry.suffix == ".json" and entry.stem == canonical:
                    return entry
        except OSError:
            return None
        return None

    def load_session(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        session_file = self._find_session_file(conversation_id)
        if session_file is None:
            return None
        try:
            data = json.loads(session_file.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("conversation_id"):
                return data
        except Exception:
            return None
        return None

    def save_session(
        self,
        conversation_id: str,
        workspace: str,
        mode: str,
        cloud_provider: str,
        local_backend: str,
        turns: List[Dict[str, str]],
        created_at: Optional[str] = None,
    ) -> bool:
        canonical = self.validate_conversation_id(conversation_id)
        now_iso = datetime.now(timezone.utc).isoformat()
        payload = {
            "conversation_id": canonical,
            "workspace": workspace,
            "mode": mode,
            "cloud_provider": cloud_provider,
            "local_backend": local_backend,
            "created_at": created_at or now_iso,
            "updated_at": now_iso,
            "turns": turns[-50:],
        }
        try:
            self.sessions_dir.mkdir(parents=True, exist_ok=True)
            # Filename is strictly derived from canonical uuid.UUID output (hex + dashes only)
            target_path = self.sessions_dir / f"{canonical}.json"
            target_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            return True
        except OSError:
            return False

    def list_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        try:
            if not self.sessions_dir.is_dir():
                return rows
            for entry in self.sessions_dir.iterdir():
                if not entry.is_file() or entry.suffix != ".json":
                    continue
                try:
                    data = json.loads(entry.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if not isinstance(data, dict) or not data.get("conversation_id"):
                    continue
                turns = data.get("turns") if isinstance(data.get("turns"), list) else []
                first_goal = str(turns[0].get("goal", "")) if turns and isinstance(turns[0], dict) else ""
                rows.append(
                    {
                        "conversation_id": str(data["conversation_id"]),
                        "workspace": str(data.get("workspace", "")),
                        "mode": str(data.get("mode", "auto")),
                        "cloud_provider": str(data.get("cloud_provider", "")),
                        "local_backend": str(data.get("local_backend", "")),
                        "created_at": str(data.get("created_at", "")),
                        "updated_at": str(data.get("updated_at", "")),
                        "turn_count": len(turns),
                        "preview": first_goal[:90],
                    }
                )
        except OSError:
            return []
        rows.sort(key=lambda r: r.get("updated_at", ""), reverse=True)
        return rows[: max(1, limit)]

    def find_latest_session(self, workspace: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Returns the most recent session (preferring the current workspace if available)."""
        sessions = self.list_sessions(limit=50)
        if not sessions:
            return None
        if workspace:
            norm_ws = os.path.realpath(os.path.abspath(os.path.expanduser(workspace)))
            for row in sessions:
                if row.get("workspace") == norm_ws:
                    loaded = self.load_session(row["conversation_id"])
                    if loaded is not None:
                        return loaded
        return self.load_session(sessions[0]["conversation_id"])


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
        approval_callback: Optional[Callable[[str, Dict[str, Any], str], Any]] = None,
    ) -> None:
        self.workspace_root = os.path.realpath(os.path.abspath(os.path.expanduser(workspace_root)))
        self.plan_mode = plan_mode
        self.auto_approve = auto_approve
        self.allow_all_edits = False
        self.allow_all_commands = False
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
        if tool_name in {"write_file", "edit_file"} and self.allow_all_edits:
            return True
        if tool_name == "run_command" and self.allow_all_commands:
            return True
        if self.approval_callback is not None:
            decision = self.approval_callback(tool_name, args, preview)
            if decision == "always":
                if tool_name in {"write_file", "edit_file"}:
                    self.allow_all_edits = True
                elif tool_name == "run_command":
                    self.allow_all_commands = True
                return True
            return bool(decision)
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
        rel = str(args.get("path", ".")).strip() or "."
        max_depth = max(1, min(4, int(args.get("max_depth", 1))))
        try:
            target = self.resolve_safe_path(rel)
            if not target.exists():
                return f"Path not found: {rel}"
            if target.is_file():
                return str(target.relative_to(self.workspace_root))

            # Explicit readability probe so macOS TCC PermissionError is never silently swallowed
            try:
                with os.scandir(target) as it:
                    _ = next(it, None)
            except PermissionError:
                return (
                    f"PermissionError: macOS denied read access to '{target}'. "
                    "Grant your terminal app access in System Settings -> Privacy & Security -> "
                    "Files and Folders (or Full Disk Access), then retry."
                )

            entries: List[str] = []
            denied_paths: List[str] = []
            base_depth = len(target.parts)

            def _on_walk_error(err: OSError) -> None:
                if isinstance(err, PermissionError) and err.filename:
                    denied_paths.append(os.path.relpath(err.filename, self.workspace_root))

            for root, dirs, files in os.walk(target, onerror=_on_walk_error):
                visible_dirs = sorted(d for d in dirs if not _is_ignored_dir(d))
                cur_depth = len(Path(root).parts) - base_depth
                rel_root = os.path.relpath(root, self.workspace_root)

                # Show subdirectories explicitly (e.g. `backend/`, `Sources/`)
                for dname in visible_dirs:
                    rel_dir = dname if rel_root == "." else os.path.join(rel_root, dname)
                    entries.append(f"{rel_dir}/")

                # Show files in this directory
                for fname in sorted(files):
                    if _is_ignored_file(fname):
                        continue
                    rel_file = fname if rel_root == "." else os.path.join(rel_root, fname)
                    entries.append(rel_file)
                    if len(entries) >= 250:
                        entries.append("... (truncated at 250 entries)")
                        break

                if len(entries) >= 250:
                    break

                if cur_depth + 1 >= max_depth:
                    dirs.clear()
                else:
                    dirs[:] = visible_dirs

            if not entries and not denied_paths:
                return "(empty directory)"
            out_lines = list(entries)
            if denied_paths:
                out_lines.append(
                    f"\n[Permission Denied on {len(denied_paths)} path(s): {', '.join(denied_paths[:5])} — "
                    "grant Files & Folders / Full Disk Access in macOS System Settings]"
                )
            return "\n".join(out_lines)
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
                dirs[:] = sorted(d for d in dirs if not _is_ignored_dir(d))
                for fname in sorted(files):
                    if _is_ignored_file(fname):
                        continue
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
        "can restore real values locally. "
        "Only call a tool when you need data not already present in the workspace overview or prior "
        "tool results, or when modifying files or running a command. "
        "When calling a tool via Markdown fence, put ONLY ONE exact tool name right after triple "
        "backticks (for example ```read_file) followed by a valid JSON object and closing ```. "
        "Never combine multiple tool names or trailing commas in a code fence header. "
        "When the task is complete, respond clearly and accurately in Markdown without extra tool blocks."
    )

    _DIRECT_LIST_FILES_RE = re.compile(
        r"^(?:"
        r"ls(?:\s+-[a-zA-Z]+)*|"
        r"dir|"
        r"(?:please\s+)?(?:can\s+you\s+|could\s+you\s+)?(?:list|show|display|print)\s+"
        r"(?:me\s+)?(?:all\s+)?(?:the\s+)?(?:files|folders|directories|contents|"
        r"files\s+and\s+(?:folders|directories)|directories\s+and\s+files)"
        r"(?:\s+(?:in|of|under|inside)\s+(?:this|the\s+current|current|my|workspace)?\s*"
        r"(?:dir|directory|folder|workspace|repo|project)?)?|"
        r"what(?:\s+files|\s+folders|'s|\s+is|\s+are)?\s+(?:in|inside)\s+"
        r"(?:this|the\s+current|current|my)\s+(?:dir|directory|folder|workspace)"
        r")(?:\s+(?:in|of|under|inside)\s+(?P<target>[./~A-Za-z0-9_-]+(?:/[A-Za-z0-9_.-]+)*))?"
        r"[\s?.!]*$",
        re.IGNORECASE,
    )
    _DIRECT_LS_TARGET_RE = re.compile(
        r"^ls(?:\s+-[a-zA-Z]+)*\s+(?P<target>[./~A-Za-z0-9_-]+(?:/[A-Za-z0-9_.-]+)*)\s*$",
        re.IGNORECASE,
    )

    def __init__(
        self,
        orchestrator: HybridOrchestrator,
        workspace_root: str = ".",
        max_steps: int = 6,
        plan_mode: bool = False,
        auto_approve: bool = False,
        approve_cloud_dispatch: bool = False,
        approval_callback: Optional[Callable[[str, Dict[str, Any], str], Any]] = None,
        cloud_approval_callback: Optional[Callable[[str, int, List[str]], Optional[str]]] = None,
        event_callback: Optional[Callable[[str, str], None]] = None,
        conversation_id: Optional[str] = None,
        session_store: Optional[CLISessionStore] = None,
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
        self.session_store = session_store or CLISessionStore()
        self._created_at: Optional[str] = None
        self._turn_history: List[Dict[str, str]] = []
        self._conversation_turns: List[str] = []
        self.resumed_turn_count: int = 0

        if conversation_id:
            self.conversation_id = CLISessionStore.validate_conversation_id(conversation_id)
            existing = self.session_store.load_session(self.conversation_id)
            if existing is not None:
                self._created_at = str(existing.get("created_at") or "") or None
                saved_turns = existing.get("turns") if isinstance(existing.get("turns"), list) else []
                for item in saved_turns:
                    if isinstance(item, dict) and item.get("goal"):
                        g = str(item.get("goal", ""))
                        a = str(item.get("final_output", ""))
                        ts = str(item.get("timestamp", ""))
                        self._turn_history.append({"goal": g, "final_output": a, "timestamp": ts})
                        self._conversation_turns.append(f"USER: {g}\nASSISTANT: {a[:600]}")
                self.resumed_turn_count = len(self._turn_history)
        else:
            self.conversation_id = CLISessionStore.new_conversation_id()

    def _emit(self, stage: str, message: str) -> None:
        if self.event_callback is not None:
            self.event_callback(stage, message)

    def _record_and_persist_turn(self, goal: str, final_answer: str) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        if not self._created_at:
            self._created_at = now_iso
        self._turn_history.append(
            {
                "goal": goal,
                "final_output": final_answer[:4000],
                "timestamp": now_iso,
            }
        )
        self._conversation_turns.append(f"USER: {goal}\nASSISTANT: {final_answer[:600]}")
        self.session_store.save_session(
            conversation_id=self.conversation_id,
            workspace=self.workspace_root,
            mode=self.orchestrator.config.compute_mode.value,
            cloud_provider=self.orchestrator.config.cloud_provider,
            local_backend=self.orchestrator.config.local_backend,
            turns=self._turn_history,
            created_at=self._created_at,
        )

    def reset_memory(self) -> None:
        self._turn_history.clear()
        self._conversation_turns.clear()
        self.resumed_turn_count = 0
        self._created_at = None
        self.conversation_id = CLISessionStore.new_conversation_id()
        self.orchestrator.guardian.vault.clear()

    def _gather_workspace_overview(self) -> str:
        files_listing, _ = self.toolbox.execute("list_files", {"path": ".", "max_depth": 2})
        return f"Workspace root: {os.path.basename(self.workspace_root)}\nFiles:\n{files_listing[:2000]}"

    def _build_local_system_instruction(self, tools: List[Dict[str, Any]]) -> str:
        """Builds system prompt with `<tools>` schema instructions for local models."""
        tools_prompt = M365ToolEmulator.format_tools_prompt(tools)
        if not tools_prompt:
            return self.AGENT_SYSTEM_PROMPT
        return f"{self.AGENT_SYSTEM_PROMPT}\n\n{tools_prompt}"

    @classmethod
    def _try_direct_workspace_tool(cls, goal: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Detects unambiguous single-intent workspace listing goals for instant grounded Station 1 execution.

        Multi-step or compound prompts (e.g. 'list files and explain auth.py') return None so the
        full autonomous hybrid reasoning loop handles them.
        """
        stripped = goal.strip()
        if not stripped or len(stripped) > 160:
            return None

        ls_match = cls._DIRECT_LS_TARGET_RE.match(stripped)
        if ls_match:
            target = ls_match.group("target").strip().rstrip("/") or "."
            return "list_files", {"path": target, "max_depth": 1}

        m = cls._DIRECT_LIST_FILES_RE.match(stripped)
        if not m:
            return None
        target = (m.group("target") or ".").strip().rstrip("/") or "."
        recursive = bool(re.search(r"\b(?:all|recursiv\w*|tree)\b", stripped, re.IGNORECASE))
        return "list_files", {"path": target, "max_depth": 2 if recursive else 1}

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
        local_system_instruction = self._build_local_system_instruction(tools)
        sec_settings = self.orchestrator.get_model_security_settings()

        if active_mode == ComputeMode.LOCAL:
            if self.orchestrator.config.local_backend == "apple_fm":
                self._emit(
                    "station1",
                    "Running 100% locally via Apple-Signed Foundation Models (Zero Hugging Face)",
                )
            else:
                self._emit(
                    "station1",
                    f"Running 100% locally on Apple Silicon ({effective_local_model or 'auto'})",
                )
            local_provider = LocalModelProvider(
                backend_type=self.orchestrator.config.local_backend,
                model=effective_local_model,
                base_url=self.orchestrator.config.local_base_url,
                litert_model_path=self.orchestrator.config.litert_model_path,
                security_settings=sec_settings,
                local_model_dir=self.orchestrator.config.local_model_dir,
            )
            resp = local_provider.generate(
                prompt=prompt_text,
                system_instruction=local_system_instruction,
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
                security_settings=sec_settings,
                local_model_dir=self.orchestrator.config.local_model_dir,
            )
            resp = local_provider.generate(
                prompt=prompt_text,
                system_instruction=local_system_instruction,
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
                    security_settings=sec_settings,
                    local_model_dir=self.orchestrator.config.local_model_dir,
                )
                resp = local_provider.generate(
                    prompt=prompt_text,
                    system_instruction=local_system_instruction,
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

        # Station 1 grounded fast path for unambiguous directory-listing goals:
        # executes WorkspaceToolbox directly without small-model hallucination or truncation.
        direct_call = None if attached_files else self._try_direct_workspace_tool(goal)
        if direct_call is not None:
            tool_name, tool_args = direct_call
            self._emit("station1", "Executing grounded local workspace tool directly on this Mac")
            self._emit("tool", f"Executing local tool `{tool_name}`")
            t_tool = time.monotonic()
            tool_out, was_approved = self.toolbox.execute(tool_name, tool_args)
            tool_ms = max(1, int((time.monotonic() - t_tool) * 1000))

            target_label = str(tool_args.get("path", "."))
            if tool_out.startswith(("PermissionError:", "list_files error:", "Directory not found:")):
                final_answer = tool_out
            elif tool_out == "(empty directory)":
                final_answer = f"**Workspace directory (`{target_label}`)** is empty."
            else:
                listing_lines = [
                    ln
                    for ln in tool_out.splitlines()
                    if ln.strip() and not ln.startswith("[Permission Denied") and not ln.startswith("... (")
                ]
                dir_count = sum(1 for ln in listing_lines if ln.endswith("/"))
                file_count = len(listing_lines) - dir_count
                final_answer = (
                    f"**Workspace directory (`{target_label}`)** — "
                    f"{dir_count} director{'y' if dir_count == 1 else 'ies'}, "
                    f"{file_count} file{'' if file_count == 1 else 's'}:\n\n"
                    f"```\n{tool_out}\n```"
                )

            step_record = AgentTurnRecord(
                step=1,
                mode_used=ComputeMode.LOCAL.value,
                provider_used="Local Workspace Toolbox",
                model_used="station1-grounded-tool",
                assistant_text=final_answer,
                tool_calls=[
                    AgentToolCall(
                        tool_name=tool_name,
                        arguments=tool_args,
                        output=tool_out[:4000],
                        approved=was_approved,
                        duration_ms=tool_ms,
                        pii_scrubbed_before_cloud=0,
                    )
                ],
                outbound_sanitized_sha256="local_only_no_outbound_payload",
                pii_flagged_count=0,
            )
            self._record_and_persist_turn(goal, final_answer)
            receipt = ExecutionReceipt(
                mode_executed=ComputeMode.LOCAL.value,
                local_model_used="station1-grounded-tool (on this Mac)",
                local_agent_location="on this Mac",
                cloud_models_used="not used",
                pii_flagged_count=0,
                pii_restored_count=0,
                pii_categories=[],
                nothing_left_mac=True,
                cloud_zero_retention=True,
                outbound_payload_sha256="local_only_no_outbound_payload",
            )
            total_ms = max(1, int((time.monotonic() - t0) * 1000))
            return AgentRunResult(
                goal=goal,
                workspace=self.workspace_root,
                final_output=final_answer,
                steps=[step_record],
                receipt=receipt,
                plan_mode=self.toolbox.plan_mode,
                total_tool_calls=1,
                total_duration_ms=total_ms,
                conversation_id=self.conversation_id,
            )

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

        self._record_and_persist_turn(goal, final_answer)

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
            conversation_id=self.conversation_id,
        )
