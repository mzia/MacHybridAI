"""Hybrid Compute Orchestrator for MacHybridAI.

Implements Perplexity-style Hybrid Compute on macOS:
- Fully Local Mode (`local`): Model and agent run 100% on this Mac. Private files
  never leave the device.
- Hybrid Mode (`hybrid`):
  1. Station 1 (`This Mac`): Local agent reads and analyzes private files on-device.
  2. Station 2 (`Privacy Gate`): On-device PII Guardian scans and masks personal/sensitive
     data with reversible stand-in tokens (`[PERSON_1]`, `[EMAIL_1]`, etc.).
  3. Station 3 (`Cloud`): Cloud model/agent (Gemini 3.8 Flash, Antigravity, OpenAI Extension,
     or M365 Copilot Proxy) conducts research and reasoning using the stand-ins.
  4. Station 4 (`Result`): Combines local analysis + cloud reasoning on this Mac and
     automatically restores real values from the local `PIIVault`.
"""

from __future__ import annotations

import os
import platform
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .guardian import GuardianPolicy, PIIGuardian, RedactionResult
from .history import (
    HistoryRetentionPolicy,
    HistoryStorageLocation,
    PromptHistoryManager,
)
from .m365_proxy import M365CopilotProxyManager, M365ModelCatalog, M365ProxySettings
from .profiler import HardwareProfiler
from .providers import (
    DEFAULT_ANTIGRAVITY_AGENT,
    DEFAULT_GEMINI_MODEL,
    AntigravityProvider,
    GeminiProvider,
    LocalModelProvider,
    M365CopilotProvider,
    OpenAICompatibleProvider,
    ProviderResponse,
    normalize_gemini_model,
)


class ComputeMode(str, Enum):
    """Execution mode for MacHybridAI tasks."""

    LOCAL = "local"
    AUTO = "auto"
    HYBRID = "hybrid"
    CLOUD = "cloud"


@dataclass
class HybridConfig:
    """User-configurable settings for MacHybridAI."""

    compute_mode: ComputeMode = ComputeMode.HYBRID
    cloud_provider: str = "gemini"  # "gemini" | "antigravity" | "openai_compatible" | "m365_copilot"
    gemini_model: str = DEFAULT_GEMINI_MODEL
    antigravity_agent: str = DEFAULT_ANTIGRAVITY_AGENT
    local_backend: str = "mlx"       # "mlx" | "litert" | "ollama" | "lmstudio"
    local_model: str = ""            # empty = auto-select best MLX model by available RAM
    local_base_url: str = "http://127.0.0.1:11434/v1"
    litert_model_path: str = "~/.litert-lm/models/gemma4-26b/model.litertlm"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4.1"
    m365_port: int = 4141
    m365_model: str = M365ModelCatalog.DEFAULT_TOOL_MODEL
    guardian_policy: GuardianPolicy = GuardianPolicy.REVERSIBLE_MASK
    history_storage: HistoryStorageLocation = HistoryStorageLocation.LOCAL
    history_retention: HistoryRetentionPolicy = HistoryRetentionPolicy.DAYS_30
    history_encrypt_at_rest: bool = False
    history_redacted_only: bool = False
    custom_sensitive_terms: List[str] = field(default_factory=list)
    allowlist_terms: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "compute_mode": self.compute_mode.value,
            "cloud_provider": self.cloud_provider,
            "gemini_model": normalize_gemini_model(self.gemini_model),
            "antigravity_agent": self.antigravity_agent,
            "local_backend": self.local_backend,
            "local_model": self.local_model,
            "local_base_url": self.local_base_url,
            "litert_model_path": self.litert_model_path,
            "openai_base_url": self.openai_base_url,
            "openai_model": self.openai_model,
            "m365_port": self.m365_port,
            "m365_model": M365ModelCatalog.resolve_model(self.m365_model),
            "guardian_policy": self.guardian_policy.value,
            "history_storage": self.history_storage.value,
            "history_retention": self.history_retention.value,
            "history_encrypt_at_rest": self.history_encrypt_at_rest,
            "history_redacted_only": self.history_redacted_only,
            "cloud_zero_retention": True,
            "custom_sensitive_terms": list(self.custom_sensitive_terms),
            "allowlist_terms": list(self.allowlist_terms),
        }


@dataclass
class StationStep:
    """Represents a single station in the Perplexity-style Hybrid Compute relay."""

    station_index: int
    station_id: str  # "this_mac" | "privacy_gate" | "cloud" | "result"
    label: str
    locality: str  # "local" | "cloud" | "shield"
    title: str
    detail: str
    status: str = "completed"
    duration_ms: int = 0
    badges: List[str] = field(default_factory=list)


@dataclass
class ExecutionReceipt:
    """'Where the work ran' transparency receipt."""

    mode_executed: str
    local_model_used: str
    local_agent_location: str
    cloud_models_used: str
    pii_flagged_count: int
    pii_restored_count: int
    pii_categories: List[str]
    nothing_left_mac: bool
    cloud_zero_retention: bool = True


@dataclass
class MacTelemetry:
    """Live Apple Silicon hardware and token telemetry."""

    architecture: str
    chip_brand: str
    cpu_percent: int
    memory_percent: int
    gpu_percent: int
    tokens_processed: int
    unified_memory_gb: int


@dataclass
class TaskExecutionResult:
    """Complete result of running a local or hybrid task."""

    task_id: str
    prompt: str
    final_output: str
    cloud_Prompt_sent: Optional[str]
    stations: List[StationStep]
    receipt: ExecutionReceipt
    telemetry: MacTelemetry
    guardian_audit: Dict[str, Any]
    session_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "session_id": self.session_id,
            "prompt": self.prompt,
            "final_output": self.final_output,
            "cloud_prompt_sent": self.cloud_Prompt_sent,
            "stations": [asdict(s) for s in self.stations],
            "receipt": asdict(self.receipt),
            "telemetry": asdict(self.telemetry),
            "guardian_audit": self.guardian_audit,
        }


class HybridOrchestrator:
    """Coordinates Local Models, Privacy Gate (PII Guardian), and Cloud Models."""

    def __init__(
        self,
        config: Optional[HybridConfig] = None,
        allowed_roots: Optional[List[str]] = None,
        history_manager: Optional[PromptHistoryManager] = None,
    ) -> None:
        self.config = config or HybridConfig()
        self.guardian = PIIGuardian(
            policy=self.config.guardian_policy,
            custom_sensitive_terms=self.config.custom_sensitive_terms,
            allowlist_terms=self.config.allowlist_terms,
        )
        self.m365_manager = M365CopilotProxyManager(
            M365ProxySettings(
                port=self.config.m365_port,
                default_model=self.config.m365_model,
            )
        )
        self.history_manager = history_manager or PromptHistoryManager(
            storage_location=self.config.history_storage,
            retention_policy=self.config.history_retention,
            encrypt_at_rest=self.config.history_encrypt_at_rest,
            redacted_only=self.config.history_redacted_only,
        )
        self.allowed_roots = [
            os.path.abspath(os.path.expanduser(r))
            for r in (allowed_roots or [os.path.expanduser("~")])
        ]

    def update_config(self, updates: Dict[str, Any]) -> HybridConfig:
        """Updates orchestrator configuration and syncs Guardian, M365, and History settings."""
        if "compute_mode" in updates:
            self.config.compute_mode = ComputeMode(updates["compute_mode"])
        if "cloud_provider" in updates:
            self.config.cloud_provider = str(updates["cloud_provider"])
        if "gemini_model" in updates:
            self.config.gemini_model = normalize_gemini_model(str(updates["gemini_model"]))
        if "antigravity_agent" in updates:
            self.config.antigravity_agent = str(updates["antigravity_agent"])
        if "local_backend" in updates:
            self.config.local_backend = str(updates["local_backend"])
        if "local_model" in updates:
            self.config.local_model = str(updates["local_model"])
        if "local_base_url" in updates:
            self.config.local_base_url = str(updates["local_base_url"])
        if "litert_model_path" in updates:
            self.config.litert_model_path = str(updates["litert_model_path"])
        if "openai_base_url" in updates:
            self.config.openai_base_url = str(updates["openai_base_url"])
        if "openai_model" in updates:
            self.config.openai_model = str(updates["openai_model"])
        if "m365_port" in updates:
            self.config.m365_port = int(updates["m365_port"])
            self.m365_manager.settings.port = self.config.m365_port
        if "m365_model" in updates:
            self.config.m365_model = M365ModelCatalog.resolve_model(str(updates["m365_model"]))
            self.m365_manager.settings.default_model = self.config.m365_model
        if "guardian_policy" in updates:
            self.config.guardian_policy = GuardianPolicy(updates["guardian_policy"])
            self.guardian.policy = self.config.guardian_policy
        if "history_storage" in updates:
            self.config.history_storage = HistoryStorageLocation(str(updates["history_storage"]))
            self.history_manager.configure(storage_location=self.config.history_storage)
        if "history_retention" in updates:
            self.config.history_retention = HistoryRetentionPolicy(str(updates["history_retention"]))
            self.history_manager.configure(retention_policy=self.config.history_retention)
        if "history_encrypt_at_rest" in updates:
            self.config.history_encrypt_at_rest = bool(updates["history_encrypt_at_rest"])
            self.history_manager.configure(encrypt_at_rest=self.config.history_encrypt_at_rest)
        if "history_redacted_only" in updates:
            self.config.history_redacted_only = bool(updates["history_redacted_only"])
            self.history_manager.configure(redacted_only=self.config.history_redacted_only)
        if "custom_sensitive_terms" in updates and isinstance(
            updates["custom_sensitive_terms"], list
        ):
            self.config.custom_sensitive_terms = [
                str(x) for x in updates["custom_sensitive_terms"]
            ]
            self.guardian.set_custom_terms(self.config.custom_sensitive_terms)
        if "allowlist_terms" in updates and isinstance(
            updates["allowlist_terms"], list
        ):
            self.config.allowlist_terms = [
                str(x) for x in updates["allowlist_terms"]
            ]
            self.guardian.set_allowlist_terms(self.config.allowlist_terms)
        return self.config

    @staticmethod
    def _normalize_attached_file_labels(file_paths: List[str]) -> List[str]:
        """Extracts safe display names for attached files (content is passed via `inline_file_context`)."""
        labels: List[str] = []
        for raw_path in file_paths:
            if not raw_path:
                continue
            cleaned = str(raw_path).replace("\\", "/").rstrip("/")
            base = cleaned.rsplit("/", 1)[-1].strip()
            if base and base not in {".", ".."}:
                labels.append(base)
        return labels

    def _resolve_smart_auto_mode(self, prompt: str) -> ComputeMode:
        """Smart Auto-Router: routes high-risk secret prompts or simple queries locally, and complex reasoning to Hybrid."""
        pre_scan = self.guardian.redact(prompt)
        high_risk = {"SECRET", "SSN", "CREDIT_CARD"}
        if any(cat in high_risk for cat in pre_scan.categories):
            return ComputeMode.LOCAL
        words = prompt.split()
        complex_keywords = {
            "benchmark",
            "compare",
            "research",
            "analyze",
            "synthesize",
            "architecture",
            "market",
            "deck",
            "multi-step",
        }
        if len(words) >= 12 or any(w.lower().strip(".,?!") in complex_keywords for w in words):
            return ComputeMode.HYBRID
        return ComputeMode.LOCAL

    def run_task(
        self,
        prompt: str,
        mode: Optional[ComputeMode] = None,
        cloud_provider: Optional[str] = None,
        file_paths: Optional[List[str]] = None,
        inline_file_context: str = "",
        tools: Optional[List[Dict[str, Any]]] = None,
        session_id: Optional[str] = None,
        save_to_history: bool = True,
        approved_sanitized_prompt: Optional[str] = None,
    ) -> TaskExecutionResult:
        """Executes a task in Fully Local, Auto Hybrid, Hybrid, or Cloud mode with PII Guardian protection."""
        requested_mode = mode or self.config.compute_mode
        active_mode = (
            self._resolve_smart_auto_mode(prompt)
            if requested_mode == ComputeMode.AUTO
            else requested_mode
        )
        active_cloud_provider = cloud_provider or self.config.cloud_provider
        task_id = f"task_{int(time.time() * 1000)}"

        loaded_files = self._normalize_attached_file_labels(file_paths or [])
        file_context = inline_file_context.strip()

        stations: List[StationStep] = []
        total_tokens = 0

        local_provider = LocalModelProvider(
            backend_type=self.config.local_backend,
            model=self.config.local_model,
            base_url=self.config.local_base_url,
            litert_model_path=self.config.litert_model_path,
        )

        # =====================================================================
        # PATH 1: FULLY LOCAL MODE (Everything stays on This Mac)
        # =====================================================================
        if active_mode == ComputeMode.LOCAL:
            t0 = time.monotonic()
            local_resp = local_provider.generate(
                prompt=prompt,
                local_files_context=file_context,
            )
            elapsed_ms = max(1, int((time.monotonic() - t0) * 1000))
            total_tokens += local_resp.tokens_used

            stations.append(
                StationStep(
                    station_index=1,
                    station_id="this_mac",
                    label="This Mac",
                    locality="local",
                    title=f"Local agent & {local_resp.model} processed task on-device",
                    detail=(
                        f"Processed {len(loaded_files)} local file(s) on this Mac. "
                        f"Nothing leaves this Mac."
                    ),
                    duration_ms=elapsed_ms,
                    badges=["Fully Local", local_resp.model, "Nothing leaves this Mac"],
                )
            )
            stations.append(
                StationStep(
                    station_index=2,
                    station_id="cloud",
                    label="Cloud models",
                    locality="local",
                    title="Cloud models not used",
                    detail="AI processing stayed 100% on your Mac. Zero Cloud AI history.",
                    duration_ms=0,
                    badges=["Not used", "Zero Cloud History"],
                )
            )
            stations.append(
                StationStep(
                    station_index=3,
                    station_id="result",
                    label="Result",
                    locality="local",
                    title="Completed on this Mac",
                    detail="Result generated locally with zero cloud transmission.",
                    duration_ms=1,
                    badges=["Verified On-Device"],
                )
            )

            receipt = ExecutionReceipt(
                mode_executed="local",
                local_model_used=f"{local_resp.model} (on this Mac)",
                local_agent_location="on this Mac",
                cloud_models_used="not used",
                pii_flagged_count=0,
                pii_restored_count=0,
                pii_categories=[],
                nothing_left_mac=True,
                cloud_zero_retention=True,
            )
            active_session_id = session_id
            if save_to_history:
                saved = self.history_manager.record_exchange(
                    prompt=prompt,
                    response_text=local_resp.output_text,
                    compute_mode="local",
                    cloud_provider="none",
                    sanitized_cloud_prompt=None,
                    pii_masked_count=0,
                    pii_restored_count=0,
                    session_id=session_id,
                )
                active_session_id = saved.session_id

            return TaskExecutionResult(
                task_id=task_id,
                session_id=active_session_id,
                prompt=prompt,
                final_output=local_resp.output_text,
                cloud_Prompt_sent=None,
                stations=stations,
                receipt=receipt,
                telemetry=self.collect_telemetry(tokens=total_tokens),
                guardian_audit=RedactionResult(
                    sanitized_text=prompt,
                    entities=[],
                    policy_applied=self.guardian.policy,
                ).to_dict(),
            )

        # =====================================================================
        # PATH 2: HYBRID / CLOUD MODE WITH ON-DEVICE PRIVACY GATE
        # =====================================================================
        # Station 1: Process private files locally on This Mac
        t_local_start = time.monotonic()
        local_resp = local_provider.generate(
            prompt=prompt,
            local_files_context=file_context,
        )
        local_ms = max(1, int((time.monotonic() - t_local_start) * 1000))
        total_tokens += local_resp.tokens_used

        stations.append(
            StationStep(
                station_index=1,
                station_id="this_mac",
                label="This Mac",
                locality="local",
                title="Local agent analyzed private files on this Mac",
                detail=(
                    f"Extracted structure from {len(loaded_files)} file(s) using "
                    f"{local_resp.model} before Privacy Gate inspection."
                ),
                duration_ms=local_ms,
                badges=["This Mac", local_resp.model],
            )
        )

        # Station 2: On-Device Privacy Gate (PII Guardian)
        t_gate_start = time.monotonic()
        combined_for_cloud = prompt
        if file_context:
            combined_for_cloud = f"{prompt}\n\nContext:\n{file_context}"

        redaction: RedactionResult = self.guardian.redact(combined_for_cloud)
        gate_ms = max(1, int((time.monotonic() - t_gate_start) * 1000))

        # Check if Guardian policy forces local execution when PII is found
        if redaction.forced_local:
            stations.append(
                StationStep(
                    station_index=2,
                    station_id="privacy_gate",
                    label="Privacy Gate",
                    locality="shield",
                    title=f"PII flagged ({redaction.pii_count}) — Forced Local Execution",
                    detail=(
                        f"Detected {', '.join(redaction.categories)}. Policy "
                        f"`force_local_on_pii` blocked cloud call and kept work on this Mac."
                    ),
                    duration_ms=gate_ms,
                    badges=["PII flagged", "Forced Local"],
                )
            )
            receipt = ExecutionReceipt(
                mode_executed="hybrid_forced_local",
                local_model_used=f"{local_resp.model} (on this Mac)",
                local_agent_location="on this Mac",
                cloud_models_used="blocked by Privacy Gate",
                pii_flagged_count=redaction.pii_count,
                pii_restored_count=0,
                pii_categories=redaction.categories,
                nothing_left_mac=True,
                cloud_zero_retention=True,
            )
            active_session_id = session_id
            if save_to_history:
                saved = self.history_manager.record_exchange(
                    prompt=prompt,
                    response_text=local_resp.output_text,
                    compute_mode="hybrid_forced_local",
                    cloud_provider="blocked",
                    sanitized_cloud_prompt=None,
                    pii_masked_count=redaction.pii_count,
                    pii_restored_count=0,
                    session_id=session_id,
                )
                active_session_id = saved.session_id

            return TaskExecutionResult(
                task_id=task_id,
                session_id=active_session_id,
                prompt=prompt,
                final_output=local_resp.output_text,
                cloud_Prompt_sent=None,
                stations=stations,
                receipt=receipt,
                telemetry=self.collect_telemetry(tokens=total_tokens),
                guardian_audit=redaction.to_dict(),
            )

        gate_badges = (
            [f"PII flagged ({redaction.pii_count})", *redaction.categories]
            if redaction.pii_flagged
            else ["No PII detected", "Verified Clean"]
        )
        stations.append(
            StationStep(
                station_index=2,
                station_id="privacy_gate",
                label="Privacy Gate",
                locality="shield",
                title=(
                    f"Privacy Gate masked {redaction.pii_count} sensitive item(s) on this Mac"
                    if redaction.pii_flagged
                    else "Privacy Gate verified prompt is free of personal identifiers"
                ),
                detail=(
                    f"Replaced {', '.join(e.replacement_token for e in redaction.entities)} "
                    f"before anything leaves your Mac."
                    if redaction.pii_flagged
                    else "Zero raw PII leaves the device."
                ),
                duration_ms=gate_ms,
                badges=gate_badges,
            )
        )

        # Station 3: Cloud Research & Reasoning (using sanitized stand-ins ONLY & store=False)
        t_cloud_start = time.monotonic()
        cloud_resp = self._invoke_cloud_provider(
            provider_name=active_cloud_provider,
            sanitized_prompt=redaction.sanitized_text,
            tools=tools,
        )
        cloud_ms = max(1, int((time.monotonic() - t_cloud_start) * 1000))
        total_tokens += cloud_resp.tokens_used

        stations.append(
            StationStep(
                station_index=3,
                station_id="cloud",
                label="Cloud",
                locality="cloud",
                title=f"Stateless Cloud reasoning via {cloud_resp.provider} ({cloud_resp.model})",
                detail=(
                    "Researched using masked stand-in tokens only. "
                    "Stateless call (store=false / temporary chat): nothing remains in Cloud AI history."
                ),
                duration_ms=cloud_ms,
                badges=[
                    cloud_resp.provider,
                    cloud_resp.model,
                    "Zero Cloud History (store=false)",
                ],
            )
        )

        # Station 4: Local Restoration & Synthesis on This Mac
        t_restore_start = time.monotonic()
        restored_cloud_text, restored_count = self.guardian.restore(cloud_resp.output_text)
        final_output = (
            f"### Hybrid Compute Synthesis\n\n"
            f"**On-Device Analysis ({local_resp.model} on This Mac):**\n"
            f"{local_resp.output_text}\n\n"
            f"**Cloud Research & Reasoning ({cloud_resp.provider} · {cloud_resp.model} · Zero Cloud History):**\n"
            f"{restored_cloud_text}"
        )
        restore_ms = max(1, int((time.monotonic() - t_restore_start) * 1000))

        stations.append(
            StationStep(
                station_index=4,
                station_id="result",
                label="Result",
                locality="local",
                title="Combined on this Mac — real values restored locally",
                detail=(
                    f"Restored {restored_count} masked stand-in token(s) from local PIIVault."
                    if restored_count > 0
                    else "Combined local private file work with stateless cloud research."
                ),
                duration_ms=restore_ms,
                badges=["Real values restored", "Hybrid Complete"],
            )
        )

        receipt = ExecutionReceipt(
            mode_executed=active_mode.value,
            local_model_used=f"{local_resp.model} (on this Mac)",
            local_agent_location="on this Mac",
            cloud_models_used=f"{cloud_resp.provider} ({cloud_resp.model})",
            pii_flagged_count=redaction.pii_count,
            pii_restored_count=restored_count,
            pii_categories=redaction.categories,
            nothing_left_mac=False,
            cloud_zero_retention=True,
        )

        active_session_id = session_id
        if save_to_history:
            saved = self.history_manager.record_exchange(
                prompt=prompt,
                response_text=final_output,
                compute_mode=active_mode.value,
                cloud_provider=cloud_resp.provider,
                sanitized_cloud_prompt=redaction.sanitized_text,
                pii_masked_count=redaction.pii_count,
                pii_restored_count=restored_count,
                session_id=session_id,
            )
            active_session_id = saved.session_id

        return TaskExecutionResult(
            task_id=task_id,
            session_id=active_session_id,
            prompt=prompt,
            final_output=final_output,
            cloud_Prompt_sent=redaction.sanitized_text,
            stations=stations,
            receipt=receipt,
            telemetry=self.collect_telemetry(tokens=total_tokens),
            guardian_audit=redaction.to_dict(),
        )

    def _invoke_cloud_provider(
        self,
        provider_name: str,
        sanitized_prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ProviderResponse:
        name = provider_name.lower().strip()
        if name == "antigravity":
            return AntigravityProvider(
                agent_id=self.config.antigravity_agent,
            ).generate(prompt=sanitized_prompt)
        if name == "m365_copilot":
            return M365CopilotProvider(
                base_url=self.m365_manager.settings.base_url,
                model=self.config.m365_model,
            ).generate(prompt=sanitized_prompt, tools=tools)
        if name == "openai_compatible":
            return OpenAICompatibleProvider(
                base_url=self.config.openai_base_url,
                model=self.config.openai_model,
            ).generate(prompt=sanitized_prompt, tools=tools)
        # Default: Google Gemini (`gemini-3.8-flash`)
        return GeminiProvider(
            model=self.config.gemini_model,
        ).generate(prompt=sanitized_prompt, tools=tools)

    @staticmethod
    def _read_cpu_percent_darwin() -> int:
        """Reads real CPU busy % on macOS using stdlib `os.getloadavg()` normalized by logical CPU count."""
        return HardwareProfiler.read_cpu_busy_percent()

    @staticmethod
    def _read_memory_percent_darwin() -> int:
        """Reads real memory pressure % on macOS via `vm_stat` + `hw.memsize`."""
        used_pct, _ = HardwareProfiler.read_memory_stats()
        return used_pct

    @staticmethod
    def _read_gpu_percent_darwin(arch: str) -> int:
        """Reads GPU engine busy % from IOKit `IOAccelerator` (`ioreg`) on Apple Silicon without requiring root."""
        if arch != "arm64" or platform.system() != "Darwin":
            return 0
        io_stats = HardwareProfiler.read_ioaccelerator_stats()
        return int(io_stats.get("device_utilization", 0))

    @staticmethod
    def collect_telemetry(tokens: int = 0) -> MacTelemetry:
        """Collects real Apple Silicon hardware metrics for the UI telemetry sparklines."""
        static = HardwareProfiler.get_static_hardware_info()
        arch = str(static["architecture"])
        chip = str(static["chip_brand"])
        mem_gb = int(static["unified_memory_gb"])

        cpu_pct = HybridOrchestrator._read_cpu_percent_darwin()
        mem_pct = HybridOrchestrator._read_memory_percent_darwin()
        gpu_pct = HybridOrchestrator._read_gpu_percent_darwin(arch)

        return MacTelemetry(
            architecture=arch,
            chip_brand=chip,
            cpu_percent=cpu_pct,
            memory_percent=mem_pct,
            gpu_percent=gpu_pct,
            tokens_processed=tokens,
            unified_memory_gb=mem_gb,
        )
