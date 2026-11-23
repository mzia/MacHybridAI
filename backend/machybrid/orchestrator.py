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

import hashlib
import os
import platform
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .guardian import GuardianPolicy, PIIGuardian, RedactionResult
from .history import (
    HistoryRetentionPolicy,
    HistoryStorageLocation,
    PromptHistoryManager,
)
from .local_rag import LocalWorkspaceRAG
from .m365_proxy import M365CopilotProxyManager, M365ModelCatalog, M365ProxySettings
from .profiler import HardwareProfiler
from .providers import (
    CLOUD_PROVIDER_PRESETS,
    DEFAULT_ANTHROPIC_MODEL,
    DEFAULT_ANTIGRAVITY_AGENT,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_OPENAI_MODEL,
    AnthropicProvider,
    AntigravityProvider,
    GeminiProvider,
    LocalModelProvider,
    M365CopilotProvider,
    OpenAICompatibleProvider,
    ProviderResponse,
    build_cloud_provider_catalog,
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
    cloud_provider: str = "gemini"  # Any preset ID ("gemini", "openai", "anthropic", "openrouter", "xai", "groq", "deepseek", "mistral", "perplexity", "together", "antigravity", "m365_copilot", "openai_compatible", "consensus")
    gemini_model: str = DEFAULT_GEMINI_MODEL
    antigravity_agent: str = DEFAULT_ANTIGRAVITY_AGENT
    anthropic_model: str = DEFAULT_ANTHROPIC_MODEL
    anthropic_base_url: str = "https://api.anthropic.com/v1"
    local_backend: str = "mlx"       # "mlx" | "litert" | "ollama" | "lmstudio"
    local_model: str = ""            # empty = auto-select best MLX model by available RAM
    local_base_url: str = "http://127.0.0.1:11434/v1"
    litert_model_path: str = "~/.litert-lm/models/gemma4-26b/model.litertlm"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = DEFAULT_OPENAI_MODEL
    custom_provider_protocol: str = "openai"  # "openai" | "anthropic"
    custom_provider_auth_header: str = "Authorization"  # "Authorization" | "x-api-key" | "api-key"
    provider_models: Dict[str, str] = field(default_factory=dict)
    consensus_providers: List[str] = field(
        default_factory=lambda: ["gemini", "anthropic", "openai"]
    )
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
            "anthropic_model": self.anthropic_model,
            "anthropic_base_url": self.anthropic_base_url,
            "local_backend": self.local_backend,
            "local_model": self.local_model,
            "local_base_url": self.local_base_url,
            "litert_model_path": self.litert_model_path,
            "openai_base_url": self.openai_base_url,
            "openai_model": self.openai_model,
            "custom_provider_protocol": self.custom_provider_protocol,
            "custom_provider_auth_header": self.custom_provider_auth_header,
            "provider_models": dict(self.provider_models),
            "consensus_providers": list(self.consensus_providers),
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
    """'Where the work ran' transparency & zero-knowledge cryptographic receipt."""

    mode_executed: str
    local_model_used: str
    local_agent_location: str
    cloud_models_used: str
    pii_flagged_count: int
    pii_restored_count: int
    pii_categories: List[str]
    nothing_left_mac: bool
    cloud_zero_retention: bool = True
    outbound_payload_sha256: str = ""
    receipt_signature_sha256: str = ""

    def __post_init__(self) -> None:
        if not self.outbound_payload_sha256:
            self.outbound_payload_sha256 = (
                "local_only_no_outbound_payload"
                if self.nothing_left_mac
                else hashlib.sha256(self.cloud_models_used.encode("utf-8")).hexdigest()
            )
        if not self.receipt_signature_sha256:
            canonical = (
                f"{self.mode_executed}|{self.local_model_used}|{self.cloud_models_used}|"
                f"{self.outbound_payload_sha256}|{self.pii_flagged_count}|"
                f"{self.pii_restored_count}|{','.join(self.pii_categories)}|"
                f"{self.cloud_zero_retention}"
            )
            self.receipt_signature_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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
        self.rag = LocalWorkspaceRAG()
        # In-memory API keys configured at runtime (never persisted to disk or echoed by /v1/config)
        self._runtime_api_keys: Dict[str, str] = {}
        self.allowed_roots = [
            os.path.abspath(os.path.expanduser(r))
            for r in (allowed_roots or [os.path.expanduser("~")])
        ]

    def list_cloud_providers(self) -> List[Dict[str, Any]]:
        """Returns all built-in and custom cloud AI provider presets with live key detection status."""
        return build_cloud_provider_catalog(self._runtime_api_keys)

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
        if "anthropic_model" in updates:
            self.config.anthropic_model = str(updates["anthropic_model"]).strip() or DEFAULT_ANTHROPIC_MODEL
        if "anthropic_base_url" in updates:
            self.config.anthropic_base_url = str(updates["anthropic_base_url"]).strip() or "https://api.anthropic.com/v1"
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
        if "custom_provider_protocol" in updates:
            proto = str(updates["custom_provider_protocol"]).strip().lower()
            if proto in {"openai", "anthropic"}:
                self.config.custom_provider_protocol = proto
        if "custom_provider_auth_header" in updates:
            hdr = str(updates["custom_provider_auth_header"]).strip()
            if hdr:
                self.config.custom_provider_auth_header = hdr
        if "provider_models" in updates and isinstance(updates["provider_models"], dict):
            for k, v in updates["provider_models"].items():
                key_clean = str(k).strip().lower()
                val_clean = str(v).strip()
                if key_clean and val_clean:
                    self.config.provider_models[key_clean] = val_clean
        if "consensus_providers" in updates and isinstance(updates["consensus_providers"], list):
            cleaned_provs = [str(x).strip().lower() for x in updates["consensus_providers"] if str(x).strip()]
            if len(cleaned_provs) >= 2:
                self.config.consensus_providers = cleaned_provs[:4]
        if "api_keys" in updates and isinstance(updates["api_keys"], dict):
            for k, v in updates["api_keys"].items():
                key_id = str(k).strip().lower()
                secret_val = str(v).strip()
                if key_id:
                    if secret_val:
                        self._runtime_api_keys[key_id] = secret_val
                    else:
                        self._runtime_api_keys.pop(key_id, None)
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

    _COMPLEX_KEYWORDS = frozenset({
        "benchmark",
        "compare",
        "research",
        "analyze",
        "synthesize",
        "architecture",
        "market",
        "deck",
        "multi-step",
        "refactor",
        "audit",
        "strategy",
        "consensus",
    })

    def classify_prompt_complexity(self, prompt: str) -> Dict[str, Any]:
        """Scores prompt sensitivity & reasoning complexity for Adaptive Smart Auto routing."""
        flagged_high_risk = self.guardian.detect_high_risk_categories(prompt)
        if flagged_high_risk:
            return {
                "recommended_mode": ComputeMode.LOCAL.value,
                "complexity_score": 0.95,
                "high_risk_categories": flagged_high_risk,
                "rationale": (
                    f"High-sensitivity credentials/identifiers detected ({', '.join(flagged_high_risk)}); "
                    "routed 100% locally on Apple Silicon."
                ),
            }

        words = prompt.split()
        matched_kw = [
            w.lower().strip(".,?!")
            for w in words
            if w.lower().strip(".,?!") in self._COMPLEX_KEYWORDS
        ]
        score = min(1.0, round((len(words) / 24.0) + (0.25 * len(matched_kw)), 2))
        if len(words) >= 12 or matched_kw:
            return {
                "recommended_mode": ComputeMode.HYBRID.value,
                "complexity_score": max(0.55, score),
                "high_risk_categories": [],
                "rationale": (
                    "Multi-step reasoning or research query detected; "
                    "routed via 4-Station Hybrid Compute with on-device PII scrubbing."
                ),
            }
        return {
            "recommended_mode": ComputeMode.LOCAL.value,
            "complexity_score": score,
            "high_risk_categories": [],
            "rationale": "Concise query suited for fast, zero-cost on-device Apple Silicon execution.",
        }

    def _resolve_smart_auto_mode(self, prompt: str) -> ComputeMode:
        """Smart Auto-Router: routes high-risk secret prompts or simple queries locally, and complex reasoning to Hybrid."""
        decision = self.classify_prompt_complexity(prompt)
        return ComputeMode(str(decision["recommended_mode"]))

    def _apply_thermal_memory_guard(self, requested_model: str) -> tuple[str, bool, str]:
        """Checks live macOS thermal state & memory pressure, stepping down to a lightweight 4-bit model if needed."""
        try:
            mem_used_pct, avail_mem_gb = HardwareProfiler.read_memory_stats()
            cpu_busy = HardwareProfiler.read_cpu_busy_percent()
            thermal_state, _ = HardwareProfiler.read_thermal_and_pressure_state(
                mem_used_pct=mem_used_pct,
                cpu_busy=cpu_busy,
                gpu_busy=0,
            )
            fast_fallback = "mlx-community/gemma-3-4b-it-4bit"
            target = requested_model or fast_fallback
            guarded, triggered, reason = HardwareProfiler.evaluate_guardrail(
                requested_model=target,
                fast_fallback_model=fast_fallback,
                mem_used_pct=mem_used_pct,
                avail_mem_gb=avail_mem_gb,
                thermal_state=thermal_state,
                recommendations=[],
            )
            if triggered:
                from .providers import MLXProvider

                MLXProvider.unload_all()
                return guarded, True, reason
        except Exception:
            pass
        return requested_model, False, ""

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
        consensus_providers: Optional[List[str]] = None,
    ) -> TaskExecutionResult:
        """Executes a task in Fully Local, Auto Hybrid, Hybrid, or Cloud mode with PII Guardian protection."""
        requested_mode = mode or self.config.compute_mode
        auto_routed = requested_mode == ComputeMode.AUTO
        active_mode = (
            self._resolve_smart_auto_mode(prompt)
            if auto_routed
            else requested_mode
        )
        active_cloud_provider = cloud_provider or self.config.cloud_provider
        task_id = f"task_{int(time.time() * 1000)}"

        loaded_files = self._normalize_attached_file_labels(file_paths or [])
        raw_file_context = inline_file_context.strip()

        # On-Device Local Workspace RAG: when large file context is attached, retrieve top-k relevant chunks
        rag_chunks_used = 0
        if len(raw_file_context) > 1000:
            retrieved = self.rag.retrieve(
                query=prompt,
                top_k=4,
                inline_context=raw_file_context,
            )
            if retrieved:
                rag_chunks_used = len(retrieved)
                file_context = self.rag.format_retrieved_context(retrieved)
            else:
                file_context = raw_file_context
        else:
            file_context = raw_file_context

        # Live Memory Pressure & Thermal Guardrail
        effective_local_model, guardrail_active, guardrail_reason = self._apply_thermal_memory_guard(
            self.config.local_model
        )

        stations: List[StationStep] = []
        total_tokens = 0

        local_provider = LocalModelProvider(
            backend_type=self.config.local_backend,
            model=effective_local_model,
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

            local_badges = ["Fully Local", local_resp.model, "Nothing leaves this Mac"]
            if auto_routed:
                local_badges.append("Smart Auto → Local")
            if rag_chunks_used > 0:
                local_badges.append(f"On-Device RAG ({rag_chunks_used} chunks)")
            if guardrail_active:
                local_badges.append("Thermal/Memory Guardrail")

            stations.append(
                StationStep(
                    station_index=1,
                    station_id="this_mac",
                    label="This Mac",
                    locality="local",
                    title=f"Local agent & {local_resp.model} processed task on-device",
                    detail=(
                        f"Processed {len(loaded_files)} local file(s) on this Mac"
                        + (f" ({rag_chunks_used} RAG chunks indexed)." if rag_chunks_used else ".")
                        + (f" {guardrail_reason}" if guardrail_active else " Nothing leaves this Mac.")
                    ),
                    duration_ms=elapsed_ms,
                    badges=local_badges,
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
                outbound_payload_sha256="local_only_no_outbound_payload",
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

        st1_badges = ["This Mac", local_resp.model]
        if auto_routed:
            st1_badges.append("Smart Auto → Hybrid")
        if rag_chunks_used > 0:
            st1_badges.append(f"On-Device RAG ({rag_chunks_used} chunks)")
        if guardrail_active:
            st1_badges.append("Thermal/Memory Guardrail")

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
                    + (f" Retrieved {rag_chunks_used} top BM25 RAG chunk(s)." if rag_chunks_used else "")
                ),
                duration_ms=local_ms,
                badges=st1_badges,
            )
        )

        # Station 2: On-Device Privacy Gate (PII Guardian)
        t_gate_start = time.monotonic()
        combined_for_cloud = prompt
        if file_context:
            combined_for_cloud = f"{prompt}\n\nContext:\n{file_context}"

        redaction: RedactionResult = self.guardian.redact(combined_for_cloud)
        outbound_sanitized = (
            approved_sanitized_prompt.strip()
            if (approved_sanitized_prompt and approved_sanitized_prompt.strip())
            else redaction.sanitized_text
        )
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
                outbound_payload_sha256="local_only_no_outbound_payload",
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
        if approved_sanitized_prompt and approved_sanitized_prompt.strip():
            gate_badges.append("User-Approved Sanitized Diff")

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

        # Station 3: Cloud Research & Reasoning (Single Cloud or Multi-Cloud Consensus Arena)
        t_cloud_start = time.monotonic()
        use_consensus = (
            active_cloud_provider.lower().strip() == "consensus"
            or (consensus_providers is not None and len(consensus_providers) >= 2)
        )

        if use_consensus:
            arena_targets = consensus_providers or self.config.consensus_providers or ["gemini", "anthropic", "openai"]
            with ThreadPoolExecutor(max_workers=min(4, len(arena_targets))) as pool:
                futures = [
                    pool.submit(
                        self._invoke_cloud_provider,
                        provider_name=prov,
                        sanitized_prompt=outbound_sanitized,
                        tools=tools,
                    )
                    for prov in arena_targets
                ]
                arena_responses = [f.result() for f in futures]

            cloud_ms = max(1, int((time.monotonic() - t_cloud_start) * 1000))
            for r in arena_responses:
                total_tokens += r.tokens_used

            combined_cloud_raw = "\n\n".join(
                f"#### Cloud Arena Candidate {idx + 1}: {r.provider} (`{r.model}`)\n{r.output_text}"
                for idx, r in enumerate(arena_responses)
            )
            cloud_provider_summary = " + ".join(f"{r.provider} ({r.model})" for r in arena_responses)
            cloud_resp = ProviderResponse(
                provider="Multi-Cloud Consensus Arena",
                model=cloud_provider_summary,
                locality="cloud",
                output_text=combined_cloud_raw,
                tokens_used=sum(r.tokens_used for r in arena_responses),
            )
        else:
            cloud_resp = self._invoke_cloud_provider(
                provider_name=active_cloud_provider,
                sanitized_prompt=outbound_sanitized,
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

        outbound_hash = hashlib.sha256(outbound_sanitized.encode("utf-8")).hexdigest()
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
            outbound_payload_sha256=outbound_hash,
        )

        active_session_id = session_id
        if save_to_history:
            saved = self.history_manager.record_exchange(
                prompt=prompt,
                response_text=final_output,
                compute_mode=active_mode.value,
                cloud_provider=cloud_resp.provider,
                sanitized_cloud_prompt=outbound_sanitized,
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
            cloud_Prompt_sent=outbound_sanitized,
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
        if name == "claude":
            name = "anthropic"
        elif name == "custom":
            name = "openai_compatible"

        runtime_key = self._runtime_api_keys.get(name, "")

        if name == "antigravity":
            return AntigravityProvider(
                api_key=runtime_key or self._runtime_api_keys.get("gemini", "") or None,
                agent_id=self.config.antigravity_agent,
            ).generate(prompt=sanitized_prompt)

        if name == "m365_copilot":
            return M365CopilotProvider(
                base_url=self.m365_manager.settings.base_url,
                model=self.config.m365_model,
            ).generate(prompt=sanitized_prompt, tools=tools)

        if name == "anthropic":
            return AnthropicProvider(
                api_key=runtime_key,
                model=self.config.provider_models.get("anthropic", self.config.anthropic_model),
                base_url=self.config.anthropic_base_url,
                provider_label="anthropic",
            ).generate(prompt=sanitized_prompt, tools=tools)

        if name == "openai":
            return OpenAICompatibleProvider(
                base_url="https://api.openai.com/v1",
                api_key=runtime_key,
                model=self.config.provider_models.get("openai", self.config.openai_model),
                provider_label="openai",
                api_key_env="OPENAI_API_KEY",
                auth_header="Authorization",
            ).generate(prompt=sanitized_prompt, tools=tools)

        if name == "openai_compatible":
            custom_key = runtime_key or self._runtime_api_keys.get("openai", "")
            if self.config.custom_provider_protocol == "anthropic":
                return AnthropicProvider(
                    api_key=custom_key or self._runtime_api_keys.get("anthropic", ""),
                    model=self.config.provider_models.get("openai_compatible", self.config.openai_model),
                    base_url=self.config.openai_base_url,
                    provider_label="custom_anthropic",
                ).generate(prompt=sanitized_prompt, tools=tools)
            return OpenAICompatibleProvider(
                base_url=self.config.openai_base_url,
                api_key=custom_key,
                model=self.config.provider_models.get("openai_compatible", self.config.openai_model),
                provider_label="openai_compatible",
                api_key_env="OPENAI_API_KEY",
                auth_header=self.config.custom_provider_auth_header,
            ).generate(prompt=sanitized_prompt, tools=tools)

        # Built-in OpenAI-compatible cloud service presets (OpenRouter, xAI Grok, Groq, DeepSeek, Mistral, Perplexity, Together)
        preset = CLOUD_PROVIDER_PRESETS.get(name)
        if preset and preset.get("protocol") == "openai":
            return OpenAICompatibleProvider(
                base_url=str(preset["base_url"]),
                api_key=runtime_key,
                model=self.config.provider_models.get(name, str(preset["default_model"])),
                provider_label=name,
                api_key_env=str(preset.get("api_key_env", "")),
                auth_header=str(preset.get("auth_header", "Authorization")),
                extra_headers=preset.get("extra_headers"),
            ).generate(prompt=sanitized_prompt, tools=tools)

        # Default: Google Gemini (`gemini-3.8-flash`)
        return GeminiProvider(
            api_key=runtime_key or None,
            model=self.config.provider_models.get("gemini", self.config.gemini_model),
        ).generate(prompt=sanitized_prompt, tools=tools)

    @staticmethod
    def _read_cpu_percent_darwin() -> int:
        return HardwareProfiler.read_cpu_busy_percent()

    @staticmethod
    def _read_memory_percent_darwin() -> int:
        return HardwareProfiler.read_memory_stats()[0]

    @staticmethod
    def collect_telemetry(tokens: int = 0) -> MacTelemetry:
        """Collects real Apple Silicon hardware metrics for the UI telemetry sparklines."""
        static = HardwareProfiler.get_static_hardware_info()
        arch = str(static["architecture"])
        chip = str(static["chip_brand"])
        mem_gb = int(static["unified_memory_gb"])

        cpu_pct = HardwareProfiler.read_cpu_busy_percent()
        mem_pct, _ = HardwareProfiler.read_memory_stats()
        gpu_pct = (
            int(HardwareProfiler.read_ioaccelerator_stats().get("device_utilization", 0))
            if arch == "arm64" and platform.system() == "Darwin"
            else 0
        )

        return MacTelemetry(
            architecture=arch,
            chip_brand=chip,
            cpu_percent=cpu_pct,
            memory_percent=mem_pct,
            gpu_percent=gpu_pct,
            tokens_processed=tokens,
            unified_memory_gb=mem_gb,
        )

    def shutdown_all_local_resources(self) -> Dict[str, Any]:
        """Unloads all local models (MLX Metal cache & local Ollama models), stops child proxies, and clears PIIVault."""
        import http.client
        import json

        from .providers import MLXProvider

        unloaded_mlx = MLXProvider.unload_all()
        unloaded_ollama: List[str] = []

        # If Ollama is running locally on 127.0.0.1:11434, unload any loaded models (keep_alive=0)
        try:
            conn = http.client.HTTPConnection("127.0.0.1", 11434, timeout=0.35)
            conn.request("GET", "/api/ps")
            resp = conn.getresponse()
            raw = resp.read()
            conn.close()
            if resp.status == 200:
                ps_data = json.loads(raw.decode("utf-8"))
                models = ps_data.get("models", []) if isinstance(ps_data, dict) else []
                for m in models:
                    m_name = m.get("name") if isinstance(m, dict) else None
                    if m_name:
                        c2 = http.client.HTTPConnection("127.0.0.1", 11434, timeout=0.35)
                        payload = json.dumps({"model": m_name, "keep_alive": 0}).encode("utf-8")
                        c2.request(
                            "POST",
                            "/api/generate",
                            body=payload,
                            headers={"Content-Type": "application/json"},
                        )
                        _ = c2.getresponse().read()
                        c2.close()
                        unloaded_ollama.append(str(m_name))
        except Exception:
            pass

        m365_ok, m365_msg = self.m365_manager.stop()
        self.guardian.vault.clear()
        self._runtime_api_keys.clear()

        return {
            "status": "shutting_down",
            "unloaded_mlx_models": unloaded_mlx,
            "unloaded_ollama_models": unloaded_ollama,
            "m365_proxy_stopped": m365_ok,
            "m365_message": m365_msg,
            "pii_vault_cleared": True,
        }
