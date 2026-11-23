"""MacHybridAI Hybrid Agentic CLI (`machybrid` / `mh`).

An Antigravity-style autonomous terminal coding & computer agent powered by
MacHybridAI's 4-Station Privacy Gate:
- Runs 100% locally on Apple Silicon (MLX / LiteRT / Ollama), in Smart Auto mode,
  or in Hybrid Mode with ANY Cloud AI service (OpenAI, Anthropic Claude, Gemini,
  OpenRouter, xAI Grok, Groq, DeepSeek, Mistral, Perplexity, Together, M365 Copilot,
  Azure/Custom, or Multi-Cloud Consensus Arena).
- Scrubs PII & secrets on-device before any cloud call, restores real values locally,
  and emits a SHA-256 Zero-Knowledge Privacy Receipt on every turn.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Sequence

from . import __version__
from .agent import AgentRunResult, HybridCLIAgent
from .guardian import GuardianPolicy
from .orchestrator import ComputeMode, HybridOrchestrator
from .profiler import HardwareProfiler
from .server import create_server


class _ANSI:
    """Minimal ANSI color palette respecting NO_COLOR and non-TTY streams."""

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def _wrap(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.enabled else text

    def bold(self, text: str) -> str:
        return self._wrap("1", text)

    def dim(self, text: str) -> str:
        return self._wrap("2", text)

    def cyan(self, text: str) -> str:
        return self._wrap("36", text)

    def green(self, text: str) -> str:
        return self._wrap("32", text)

    def yellow(self, text: str) -> str:
        return self._wrap("33", text)

    def magenta(self, text: str) -> str:
        return self._wrap("35", text)

    def red(self, text: str) -> str:
        return self._wrap("31", text)


def _make_ansi(no_color: bool = False) -> _ANSI:
    if no_color or os.environ.get("NO_COLOR"):
        return _ANSI(False)
    return _ANSI(sys.stdout.isatty())


def _print_banner(
    ansi: _ANSI,
    orchestrator: HybridOrchestrator,
    workspace: str,
    plan_mode: bool,
    approve_cloud: bool,
) -> None:
    hw = HardwareProfiler.get_static_hardware_info()
    chip = hw.get("chip_brand", "Apple Silicon")
    ram_gb = hw.get("unified_memory_gb", 8)
    print(
        ansi.bold(ansi.cyan(f"\n  MacHybridAI CLI v{__version__}"))
        + ansi.dim(" — Hybrid Split-Compute Agentic Studio (M⇄AI)")
    )
    print(
        ansi.dim(
            f"  Hardware : {chip} ({ram_gb} GB Unified RAM) · Workspace: {workspace}"
        )
    )
    mode_str = orchestrator.config.compute_mode.value.upper()
    prov_str = orchestrator.config.cloud_provider
    flags: List[str] = ["Zero Cloud History (store=false)"]
    if plan_mode:
        flags.append("PLAN MODE (Read-Only)")
    if approve_cloud:
        flags.append("CLOUD DIFF GATE ON")
    print(
        f"  Mode     : {ansi.cyan(mode_str)}  ·  Cloud: {ansi.magenta(prov_str)}  ·  "
        + ansi.green(" · ".join(flags))
    )
    print(ansi.dim("  Type a goal or /help for slash commands (/mode, /provider, /plan, /hardware, /quit).\n"))


def _print_receipt(ansi: _ANSI, result: AgentRunResult, verbose: bool = False) -> None:
    r = result.receipt
    badge = (
        ansi.green("100% LOCAL · Nothing left this Mac")
        if r.nothing_left_mac
        else ansi.magenta(f"HYBRID · {r.cloud_models_used} · Zero Cloud History")
    )
    print(
        ansi.dim("  ─── Receipt ")
        + badge
        + ansi.dim(
            f" · PII masked: {r.pii_flagged_count} · restored: {r.pii_restored_count}"
            f" · tools: {result.total_tool_calls} · {result.total_duration_ms}ms"
        )
    )
    if verbose:
        print(ansi.dim(f"      Local Model  : {r.local_model_used}"))
        print(ansi.dim(f"      Cloud Models : {r.cloud_models_used}"))
        print(ansi.dim(f"      Categories   : {', '.join(r.pii_categories) or 'none'}"))
        print(ansi.dim(f"      Payload SHA  : {r.outbound_payload_sha256}"))
        print(ansi.dim(f"      Receipt Sig  : {r.receipt_signature_sha256}"))


def _public_provider_rows(orchestrator: HybridOrchestrator) -> List[Dict[str, Any]]:
    """Returns non-sensitive provider display metadata safe for CLI output."""
    rows: List[Dict[str, Any]] = []
    for p in orchestrator.list_cloud_providers():
        rows.append(
            {
                "id": str(p["id"]),
                "name": str(p["name"]),
                "protocol": str(p["protocol"]),
                "base_url": str(p["base_url"]),
                "default_model": str(p["default_model"]),
                "recommended_models": list(p["recommended_models"]),
                "env_var": str(p.get("env_var", "")),
                "configured": bool(p.get("configured", False)),
            }
        )
    return rows


def _print_providers_table(ansi: _ANSI, orchestrator: HybridOrchestrator) -> None:
    providers = _public_provider_rows(orchestrator)
    print(ansi.bold("\nSupported Cloud AI Providers (All Behind On-Device Privacy Gate):"))
    for p in providers:
        is_ready = bool(p["configured"])
        env_var_name = str(p["env_var"])
        status_badge = (
            ansi.green("READY")
            if is_ready
            else ansi.dim(f"set {env_var_name}" if env_var_name else "local proxy")
        )
        active_mark = ansi.cyan("◀ active") if p["id"] == orchestrator.config.cloud_provider else ""
        print(
            f"  {ansi.bold(str(p['id']).ljust(18))} "
            f"{str(p['protocol']).ljust(11)} "
            f"{str(p['default_model']).ljust(36)} "
            f"{status_badge} {active_mark}"
        )
    print(
        ansi.dim(
            "\n  Tip: Use `/provider anthropic` or `/provider openai` or `/provider consensus`, "
            "and `/key <provider> <value>` to load a RAM-only credential.\n"
        )
    )


def _print_hardware_summary(ansi: _ANSI) -> None:
    prof = HardwareProfiler.profile()
    print(ansi.bold(f"\nApple Silicon Hardware Profile — {prof.chip_brand}"))
    print(
        f"  CPU/GPU  : {prof.cpu_cores_total} CPU ({prof.cpu_cores_performance}P + {prof.cpu_cores_efficiency}E) "
        f"· {prof.gpu_cores}-Core GPU ({prof.gpu_architecture})"
    )
    print(
        f"  Memory   : {prof.unified_memory_gb} GB Unified · Metal Working Set {prof.metal_working_set_gb:.1f} GB "
        f"· Used {prof.memory_used_percent}% ({prof.available_memory_gb:.1f} GB free)"
    )
    print(
        f"  Status   : Thermal={prof.thermal_state} · Pressure={prof.memory_pressure_level} "
        f"· Active Local Model={ansi.cyan(prof.selected_local_model)}"
    )
    if prof.guardrail_triggered:
        print(ansi.yellow(f"  Guardrail: {prof.guardrail_reason}"))
    print()


def _interactive_tool_approval(ansi: _ANSI, tool_name: str, args: Dict[str, Any], preview: str) -> bool:
    print(ansi.yellow(f"\n  [Approval Required] Tool `{tool_name}`"))
    print(ansi.dim(f"  {preview}"))
    try:
        answer = input(ansi.bold("  Approve this local workspace action? [y/N]: ")).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer in {"y", "yes"}


def _interactive_cloud_approval(
    ansi: _ANSI,
    sanitized_payload: str,
    pii_count: int,
    categories: List[str],
) -> Optional[str]:
    print(ansi.yellow(f"\n  [Station 2 Cloud Diff Gate] {pii_count} PII item(s) masked ({', '.join(categories) or 'clean'})"))
    print(ansi.dim("  Sanitized payload preview (first 600 chars):"))
    print(ansi.dim("  " + sanitized_payload[:600].replace("\n", "\n  ")))
    try:
        answer = input(ansi.bold("  Dispatch sanitized payload to Cloud? [Y/n (n=run locally)]: ")).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return None
    if answer in {"n", "no"}:
        return None
    return sanitized_payload


def handle_slash_command(
    raw_line: str,
    agent: HybridCLIAgent,
    orchestrator: HybridOrchestrator,
    ansi: _ANSI,
    last_result_box: List[Optional[AgentRunResult]],
) -> bool:
    """Handles a `/command` in the interactive CLI REPL. Returns False when the user wants to quit."""
    parts = raw_line.strip().split(maxsplit=2)
    cmd = parts[0].lower()

    if cmd in {"/quit", "/exit", "/q"}:
        return False

    if cmd == "/help":
        print(
            ansi.bold("\nMacHybridAI Agentic CLI Slash Commands:\n")
            + "  /mode local|auto|hybrid    Switch Split-Compute execution mode\n"
            + "  /provider <id>             Switch Cloud AI (openai, anthropic, gemini, openrouter, xai, groq, deepseek, mistral, perplexity, together, m365_copilot, consensus)\n"
            + "  /providers                 List all supported Cloud AI providers & key status\n"
            + "  /key <provider> <secret>   Load a RAM-only API key (never written to disk)\n"
            + "  /plan                      Toggle read-only Plan Mode (blocks writes & shell)\n"
            + "  /approve                   Toggle Interactive Cloud Diff Approval Gate\n"
            + "  /yolo                      Toggle auto-approval of workspace edits & commands\n"
            + "  /inspect <text>            Test Privacy Gate PII masking & local restoration\n"
            + "  /hardware                  Inspect Apple Silicon SoC, Metal RAM & thermal state\n"
            + "  /benchmark                 Run 1-click Apple Silicon Metal inference benchmark\n"
            + "  /receipt                   Show full SHA-256 cryptographic receipt of last turn\n"
            + "  /clear                     Clear agent memory & local PIIVault\n"
            + "  /quit                      Unload local models, wipe RAM keys & exit\n"
        )
        return True

    if cmd == "/mode":
        if len(parts) < 2:
            print(f"  Current mode: {ansi.cyan(orchestrator.config.compute_mode.value)}")
            return True
        try:
            orchestrator.update_config({"compute_mode": parts[1].lower()})
            print(f"  Switched compute mode to {ansi.cyan(orchestrator.config.compute_mode.value.upper())}")
        except ValueError:
            print(ansi.red("  Invalid mode. Choose: local, auto, or hybrid."))
        return True

    if cmd == "/provider":
        if len(parts) < 2:
            print(f"  Current cloud provider: {ansi.magenta(orchestrator.config.cloud_provider)}")
            return True
        orchestrator.update_config({"cloud_provider": parts[1].lower()})
        print(f"  Switched cloud provider to {ansi.magenta(orchestrator.config.cloud_provider)}")
        return True

    if cmd == "/providers":
        _print_providers_table(ansi, orchestrator)
        return True

    if cmd == "/key":
        if len(parts) < 3:
            print(ansi.yellow("  Usage: /key <provider_id> <api_key>  (stored strictly in RAM)"))
            return True
        prov_id, secret = parts[1].lower(), parts[2].strip()
        orchestrator.update_config({"api_keys": {prov_id: secret}})
        print(ansi.green(f"  Loaded in-memory API key for `{prov_id}` (never persisted to disk)."))
        return True

    if cmd == "/plan":
        agent.toolbox.plan_mode = not agent.toolbox.plan_mode
        state = ansi.yellow("ON (Read-Only)") if agent.toolbox.plan_mode else ansi.green("OFF (Read/Write)")
        print(f"  Plan Mode is now {state}")
        return True

    if cmd == "/approve":
        agent.approve_cloud_dispatch = not agent.approve_cloud_dispatch
        state = ansi.yellow("ON") if agent.approve_cloud_dispatch else ansi.dim("OFF")
        print(f"  Interactive Cloud Diff Approval Gate is now {state}")
        return True

    if cmd == "/yolo":
        agent.toolbox.auto_approve = not agent.toolbox.auto_approve
        state = ansi.yellow("ON (Auto-Approve Tools)") if agent.toolbox.auto_approve else ansi.green("OFF (Prompt Before Mutating)")
        print(f"  Auto-Approve is now {state}")
        return True

    if cmd == "/inspect":
        sample = raw_line[len("/inspect") :].strip()
        if not sample:
            print(ansi.yellow("  Usage: /inspect <text with emails/names/secrets>"))
            return True
        red = orchestrator.guardian.redact(sample)
        restored, _ = orchestrator.guardian.restore(red.sanitized_text)
        print(f"  {ansi.yellow('Sanitized:')} {red.sanitized_text}")
        print(f"  {ansi.green('Restored :')} {restored}")
        print(ansi.dim(f"  Flagged  : {red.pii_count} item(s) ({', '.join(red.categories) or 'none'})"))
        return True

    if cmd == "/hardware":
        _print_hardware_summary(ansi)
        return True

    if cmd == "/benchmark":
        print(ansi.dim("  Running Apple Silicon Metal benchmark..."))
        bench = HardwareProfiler.run_benchmark()
        print(
            f"  {ansi.bold(bench.model_id)} ({bench.backend}) · "
            f"TTFT {bench.ttft_ms}ms · Prefill {bench.prefill_tps} tok/s · "
            f"Decode {ansi.green(str(bench.decode_tps) + ' tok/s')} · Peak {bench.peak_memory_gb} GB"
        )
        return True

    if cmd == "/receipt":
        if last_result_box and last_result_box[0] is not None:
            _print_receipt(ansi, last_result_box[0], verbose=True)
        else:
            print(ansi.dim("  No completed turn yet."))
        return True

    if cmd == "/clear":
        agent.reset_memory()
        print(ansi.green("  Cleared conversation context and local PIIVault."))
        return True

    print(ansi.red(f"  Unknown command `{cmd}`. Type /help for available commands."))
    return True


def _run_interactive_repl(
    agent: HybridCLIAgent,
    orchestrator: HybridOrchestrator,
    ansi: _ANSI,
) -> int:
    _print_banner(
        ansi,
        orchestrator,
        agent.workspace_root,
        agent.toolbox.plan_mode,
        agent.approve_cloud_dispatch,
    )
    last_result_box: List[Optional[AgentRunResult]] = [None]

    try:
        while True:
            mode_tag = orchestrator.config.compute_mode.value
            prov_tag = (
                "local"
                if orchestrator.config.compute_mode == ComputeMode.LOCAL
                else orchestrator.config.cloud_provider
            )
            prompt_prefix = ansi.bold(ansi.cyan(f"M⇄AI [{mode_tag}:{prov_tag}]> "))
            try:
                user_line = input(prompt_prefix).strip()
            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                print()
                continue

            if not user_line:
                continue

            if user_line.startswith("/"):
                should_continue = handle_slash_command(
                    user_line, agent, orchestrator, ansi, last_result_box
                )
                if not should_continue:
                    break
                continue

            res = agent.run(goal=user_line)
            last_result_box[0] = res
            print()
            print(res.final_output)
            print()
            _print_receipt(ansi, res, verbose=False)
            print()
    finally:
        orchestrator.shutdown_all_local_resources()
        print(ansi.dim("  Cleaned up local models, RAM API keys, and PIIVault. Goodbye."))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="machybrid",
        description=(
            "MacHybridAI — Antigravity-style Hybrid Split-Compute Agentic CLI "
            "(Apple Silicon Local + On-Device Privacy Gate + Any Cloud AI)"
        ),
    )
    parser.add_argument("--version", action="version", version=f"machybrid {__version__}")
    parser.add_argument(
        "--mode",
        choices=["local", "auto", "hybrid"],
        default="auto",
        help="Split-compute mode (default: auto)",
    )
    parser.add_argument(
        "--provider",
        default="gemini",
        help=(
            "Cloud AI provider: gemini, openai, anthropic, openrouter, xai, groq, "
            "deepseek, mistral, perplexity, together, m365_copilot, openai_compatible, consensus"
        ),
    )
    parser.add_argument("--model", default="", help="Override active cloud model identifier")
    parser.add_argument("--base-url", default="", help="Custom OpenAI/Anthropic base URL")
    parser.add_argument(
        "--protocol",
        choices=["openai", "anthropic"],
        default="openai",
        help="Wire protocol when using --provider openai_compatible",
    )
    parser.add_argument(
        "--workspace",
        default=".",
        help="Workspace directory for local agent tools (default: current directory)",
    )
    parser.add_argument(
        "--file",
        action="append",
        default=[],
        help="Attach a local workspace file to context (repeatable)",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Read-only Plan Mode (allows read/search tools, blocks file writes & commands)",
    )
    parser.add_argument(
        "--approve-cloud",
        action="store_true",
        help="Pause to preview & approve the Station 2 sanitized payload before cloud dispatch",
    )
    parser.add_argument(
        "--yolo",
        action="store_true",
        help="Auto-approve local workspace edits and commands without prompting",
    )
    parser.add_argument("--max-steps", type=int, default=6, help="Max autonomous agent tool steps (1-12)")
    parser.add_argument("--json", action="store_true", help="Output structured JSON")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors")

    subparsers = parser.add_subparsers(dest="subcommand")

    p_run = subparsers.add_parser("run", help="Run a one-shot autonomous hybrid agent task")
    p_run.add_argument("goal", nargs="+", help="Task or coding goal for the hybrid agent")

    p_inspect = subparsers.add_parser("inspect", help="Scan text with the on-device Privacy Gate")
    p_inspect.add_argument("text", nargs="+", help="Text to audit for PII & secrets")
    p_inspect.add_argument(
        "--policy",
        choices=[p.value for p in GuardianPolicy],
        default=GuardianPolicy.REVERSIBLE_MASK.value,
    )

    subparsers.add_parser("providers", help="List all supported Cloud AI providers & key status")
    subparsers.add_parser("hardware", help="Inspect Apple Silicon SoC, Metal RAM & local model cache")

    p_bench = subparsers.add_parser("benchmark", help="Run Apple Silicon Metal inference benchmark")
    p_bench.add_argument("--local-model", default=None, help="Specific MLX model ID to benchmark")

    p_proxy = subparsers.add_parser(
        "proxy",
        help="Start drop-in OpenAI-compatible privacy proxy (/v1/chat/completions) for IDEs",
    )
    p_proxy.add_argument("--host", default="127.0.0.1")
    p_proxy.add_argument("--port", type=int, default=8765)

    return parser


def _normalize_shorthand_args(raw_args: List[str]) -> List[str]:
    """Inserts `run` before the first positional argument if it is not a known subcommand.

    Enables both `machybrid "Refactor auth.py"` and
    `machybrid --mode hybrid --provider anthropic "Refactor auth.py"`.
    """
    known_subcommands = {"run", "inspect", "providers", "hardware", "benchmark", "proxy"}
    value_flags = {
        "--mode",
        "--provider",
        "--model",
        "--base-url",
        "--protocol",
        "--workspace",
        "--file",
        "--max-steps",
    }
    idx = 0
    n = len(raw_args)
    while idx < n:
        tok = raw_args[idx]
        if tok in {"-h", "--help", "--version"}:
            return raw_args
        if tok in value_flags:
            idx += 2
            continue
        if tok.startswith("-"):
            idx += 1
            continue
        if tok not in known_subcommands:
            return [*raw_args[:idx], "run", *raw_args[idx:]]
        return raw_args
    return raw_args


def main(argv: Optional[Sequence[str]] = None) -> int:
    raw_args = _normalize_shorthand_args(list(argv) if argv is not None else sys.argv[1:])

    parser = build_parser()
    args = parser.parse_args(raw_args)
    ansi = _make_ansi(no_color=args.no_color or args.json)

    orchestrator = HybridOrchestrator()
    cfg_updates: Dict[str, Any] = {
        "compute_mode": args.mode,
        "cloud_provider": args.provider,
        "custom_provider_protocol": args.protocol,
    }
    if args.base_url:
        cfg_updates["openai_base_url"] = args.base_url
        if args.provider in {"anthropic", "claude"}:
            cfg_updates["anthropic_base_url"] = args.base_url
    if args.model:
        cfg_updates["provider_models"] = {args.provider.lower(): args.model}
        if args.provider == "gemini":
            cfg_updates["gemini_model"] = args.model
        elif args.provider in {"anthropic", "claude"}:
            cfg_updates["anthropic_model"] = args.model
        else:
            cfg_updates["openai_model"] = args.model
    orchestrator.update_config(cfg_updates)

    if args.subcommand == "providers":
        catalog = _public_provider_rows(orchestrator)
        if args.json:
            print(json.dumps({"active_provider": orchestrator.config.cloud_provider, "providers": catalog}, indent=2))
        else:
            _print_providers_table(ansi, orchestrator)
        return 0

    if args.subcommand == "hardware":
        prof = HardwareProfiler.profile()
        if args.json:
            print(json.dumps(prof.to_dict(), indent=2))
        else:
            _print_hardware_summary(ansi)
        return 0

    if args.subcommand == "benchmark":
        bench = HardwareProfiler.run_benchmark(model_id=args.local_model)
        if args.json:
            print(json.dumps(bench.to_dict(), indent=2))
        else:
            print(
                f"{ansi.bold(bench.model_id)} ({bench.backend}) · "
                f"TTFT {bench.ttft_ms}ms · Prefill {bench.prefill_tps} tok/s · "
                f"Decode {ansi.green(str(bench.decode_tps) + ' tok/s')} · Peak {bench.peak_memory_gb} GB"
            )
        return 0

    if args.subcommand == "inspect":
        text = " ".join(args.text)
        policy = GuardianPolicy(args.policy)
        red = orchestrator.guardian.redact(text, policy_override=policy)
        restored, restored_n = orchestrator.guardian.restore(red.sanitized_text)
        out = red.to_dict()
        out["restored_preview"] = restored
        out["restored_count"] = restored_n
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            print(f"{ansi.yellow('Sanitized:')} {red.sanitized_text}")
            print(f"{ansi.green('Restored :')} {restored}")
            print(ansi.dim(f"Flagged  : {red.pii_count} ({', '.join(red.categories) or 'none'})"))
        return 0

    if args.subcommand == "proxy":
        server = create_server(host=args.host, port=args.port, orchestrator=orchestrator)
        print(
            ansi.bold(ansi.cyan(f"MacHybridAI OpenAI-Compatible Privacy Proxy listening on http://{args.host}:{args.port}/v1"))
        )
        print(
            ansi.dim(
                "Models: machybrid-auto, machybrid-local, machybrid-openai, machybrid-claude, "
                "machybrid-openrouter, machybrid-consensus"
            )
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            orchestrator.shutdown_all_local_resources()
            server.server_close()
        return 0

    def _on_event(stage: str, msg: str) -> None:
        if args.json:
            return
        tag_map = {
            "station1": ansi.cyan("  [Station 1 · This Mac]"),
            "station2": ansi.yellow("  [Station 2 · Privacy Gate]"),
            "station3": ansi.magenta("  [Station 3 · Cloud]"),
            "tool": ansi.cyan("  [Tool]"),
            "guardrail": ansi.yellow("  [Guardrail]"),
        }
        print(f"{tag_map.get(stage, ansi.dim('  [Agent]'))} {msg}")

    agent = HybridCLIAgent(
        orchestrator=orchestrator,
        workspace_root=args.workspace,
        max_steps=args.max_steps,
        plan_mode=args.plan,
        auto_approve=args.yolo,
        approve_cloud_dispatch=args.approve_cloud,
        approval_callback=(
            None
            if args.json
            else (lambda name, tool_args, preview: _interactive_tool_approval(ansi, name, tool_args, preview))
        ),
        cloud_approval_callback=(
            None
            if args.json
            else (lambda payload, count, cats: _interactive_cloud_approval(ansi, payload, count, cats))
        ),
        event_callback=_on_event,
    )

    if args.subcommand == "run":
        goal_text = " ".join(args.goal)
        try:
            result = agent.run(
                goal=goal_text,
                attached_files=args.file,
            )
            if args.json:
                print(json.dumps(result.to_dict(), indent=2))
            else:
                print()
                print(result.final_output)
                print()
                _print_receipt(ansi, result, verbose=True)
        finally:
            orchestrator.shutdown_all_local_resources()
        return 0

    return _run_interactive_repl(agent, orchestrator, ansi)


if __name__ == "__main__":
    raise SystemExit(main())
