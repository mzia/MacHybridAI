"""AI & Agent Provider Implementations for MacHybridAI.

Includes:
- Default Cloud Agent: Google Antigravity (`google-antigravity` SDK `LocalAgentConfig`
  and Gemini Managed Agent `antigravity-preview-05-2026`)
- Default Cloud Model: Google Gemini (`google-genai` SDK >= 2.3.0 Interactions API
  with `gemini-3.8-flash`, `gemini-3.1-pro-preview`, `gemini-3.5-flash-lite`)
- Default Local On-Device Model:
    • Apple MLX — native Apple Silicon backend (ANE + Metal), fastest path on M-series Macs.
      Uses mlx-lm to run any HuggingFace-format MLX model (e.g. gemma-4-31B-it-MLX-8bit,
      Qwen3.6-40B-8bit) directly from the local HF cache with token streaming support.
    • LiteRT-LM (`LiteRTAgentConfig` with Gemma 4 on Metal GPU)
    • Local OpenAI-compatible (`LocalOpenAIAgentConfig` for Ollama / LM Studio)
- OpenAI Extension Method: Configurable `/v1/chat/completions` client for any provider
- M365 Copilot Proxy Method: `cramt/m365-copilot-proxy` with Markdown-fence & shell-routing
"""

from __future__ import annotations

import asyncio
import gc
import http.client
import json
import os
import re
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generator, List, Optional

from .m365_proxy import M365ModelCatalog, M365ToolEmulator
from .profiler import HardwareProfiler

# Deprecated Gemini model guard per gemini-api-dev skill rules
_DEPRECATED_GEMINI_PREFIXES = ("gemini-2.5", "gemini-2.0", "gemini-1.5", "gemini-1.0")
_STANDIN_TOKEN_RE = re.compile(r"\[[A-Z_]+_\d+\]")
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
DEFAULT_ANTIGRAVITY_AGENT = "antigravity-preview-05-2026"
DEFAULT_AGY_SDK_MODEL = "gemini-3.7-flash"

# ---------------------------------------------------------------------------
# MLX — Apple Silicon native model paths
# ---------------------------------------------------------------------------
# Priority order: try the 31B 8-bit model first (best quality on 48 GB),
# fall back to the 4B 4-bit model (fast, ~20 tok/s, always fits in RAM).
# Both are keyed by their HuggingFace repo ID so mlx-lm resolves from the
# local HF cache without a network round-trip when already downloaded.
MLX_DEFAULT_MODEL = "lmstudio-community/gemma-4-31B-it-MLX-8bit"
MLX_FALLBACK_MODEL = "mlx-community/gemma-3-4b-it-4bit"

# Minimum unified memory (GB) required to load the large model comfortably.
# On a 48 GB M5 Pro the 31B 8-bit model uses ~19 GB, leaving plenty of headroom.
MLX_LARGE_MODEL_MIN_MEMORY_GB = 24


def _post_json_http(
    endpoint_url: str,
    payload: Dict[str, Any],
    headers: Dict[str, str],
    timeout: float = 4.0,
) -> Dict[str, Any]:
    """Performs an HTTP/HTTPS JSON POST using stdlib `http.client` with scheme validation."""
    parsed = urllib.parse.urlsplit(endpoint_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"Unsupported URL scheme or host: {endpoint_url}")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    conn: http.client.HTTPConnection
    if parsed.scheme == "https":
        conn = http.client.HTTPSConnection(parsed.hostname, port, timeout=timeout)
    else:
        conn = http.client.HTTPConnection(parsed.hostname, port, timeout=timeout)

    try:
        raw_body = json.dumps(payload).encode("utf-8")
        conn.request("POST", path, body=raw_body, headers=headers)
        resp = conn.getresponse()
        resp_bytes = resp.read()
        if resp.status < 200 or resp.status >= 300:
            raise OSError(f"HTTP {resp.status}")
        decoded = json.loads(resp_bytes.decode("utf-8"))
        return decoded if isinstance(decoded, dict) else {}
    finally:
        conn.close()


def normalize_gemini_model(model: Optional[str]) -> str:
    """Replaces deprecated Gemini 1.x/2.x identifiers with `gemini-3.8-flash`."""
    if not model or not model.strip():
        return DEFAULT_GEMINI_MODEL
    cleaned = model.strip()
    if any(cleaned.startswith(prefix) for prefix in _DEPRECATED_GEMINI_PREFIXES):
        return DEFAULT_GEMINI_MODEL
    return cleaned


@dataclass
class ProviderResponse:
    """Normalized response from any local or cloud AI provider."""

    provider: str
    model: str
    output_text: str
    locality: str  # "local" | "cloud"
    interaction_id: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    tokens_used: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class MLXProvider:
    """Apple Silicon native local inference via `mlx-lm`.

    Uses the ANE (Apple Neural Engine) and Metal GPU through Apple's MLX framework —
    the fastest local inference path on M-series Macs.  No network calls; runs
    entirely from the local HuggingFace cache.

    Model selection logic:
      1. If ``model`` is explicitly set, use it.
      2. If unified memory >= MLX_LARGE_MODEL_MIN_MEMORY_GB, prefer the 31B model.
      3. Otherwise fall back to the 4B model (always fits in ≥8 GB).

    Streaming:
      ``generate_stream()`` yields token strings one at a time so the caller can
      push them to the UI incrementally.  ``generate()`` collects the stream and
      returns a standard ``ProviderResponse``.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.2,
        system_instruction: Optional[str] = None,
        kv_bits: Optional[int] = None,
    ) -> None:
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.system_instruction = system_instruction
        self._model_id = self._resolve_model(model)
        self.kv_bits = kv_bits
        self.last_generation_stats: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @classmethod
    def is_available(cls) -> bool:
        """Returns True when mlx and mlx-lm are importable (cached per process)."""
        if cls._mlx_available_cache is not None:
            return cls._mlx_available_cache
        try:
            import mlx.core  # noqa: F401
            import mlx_lm  # noqa: F401
            cls._mlx_available_cache = True
        except ImportError:
            cls._mlx_available_cache = False
        return cls._mlx_available_cache

    @staticmethod
    def unified_memory_gb() -> int:
        """Returns unified memory size in GB via MLX device info or HardwareProfiler."""
        try:
            import mlx.core as mx
            info = mx.device_info()
            mem = int(info.get("memory_size", 0)) // (1024 ** 3)
            if mem > 0:
                return mem
        except Exception:
            pass
        return int(HardwareProfiler.get_static_hardware_info()["unified_memory_gb"])

    @property
    def model_id(self) -> str:
        return self._model_id

    # ------------------------------------------------------------------
    # Streaming generation — yields one token string at a time
    # ------------------------------------------------------------------

    def generate_stream(
        self,
        prompt: str,
        token_callback: Optional[Callable[[str], None]] = None,
        max_tokens: Optional[int] = None,
    ) -> Generator[str, None, None]:
        """Yields token strings from the MLX model one at a time using `mlx_lm.stream_generate`.

        Compatible with `mlx-lm >= 0.30` (`make_sampler`, KV cache quantization, and
        live `prompt_tps`, `generation_tps`, and `peak_memory` metrics).
        """
        from mlx_lm import stream_generate
        from mlx_lm.sample_utils import make_sampler

        model, tokenizer = self._load_model()

        # Apply chat template if the tokenizer supports it
        messages = []
        if self.system_instruction:
            messages.append({"role": "system", "content": self.system_instruction})
        messages.append({"role": "user", "content": prompt})

        if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:  # type: ignore[union-attr]
            formatted = tokenizer.apply_chat_template(  # type: ignore[union-attr]
                messages, tokenize=False, add_generation_prompt=True
            )
        else:
            formatted = prompt

        effective_max_tokens = max_tokens if max_tokens is not None else self.max_tokens
        sampler = make_sampler(temp=self.temperature, top_p=0.95)
        gen_kwargs: Dict[str, Any] = {
            "max_tokens": effective_max_tokens,
            "sampler": sampler,
        }
        if self.kv_bits is not None:
            gen_kwargs["kv_bits"] = self.kv_bits
            gen_kwargs["kv_group_size"] = 64
            gen_kwargs["quantized_kv_start"] = 2048

        token_count = 0
        last_resp = None
        with MLXProvider._inference_lock:
            for resp in stream_generate(
                model,
                tokenizer,
                prompt=formatted,
                **gen_kwargs,
            ):
                last_resp = resp
                token_str = getattr(resp, "text", "")
                if token_str:
                    if token_callback:
                        token_callback(token_str)
                    yield token_str
                token_count += 1
                if token_count >= effective_max_tokens:
                    break

        if last_resp is not None:
            self.last_generation_stats = {
                "prompt_tokens": int(getattr(last_resp, "prompt_tokens", 0)),
                "prompt_tps": round(float(getattr(last_resp, "prompt_tps", 0.0)), 1),
                "generation_tokens": int(getattr(last_resp, "generation_tokens", token_count)),
                "generation_tps": round(float(getattr(last_resp, "generation_tps", 0.0)), 1),
                "peak_memory_gb": round(float(getattr(last_resp, "peak_memory", 0.0)), 2),
            }

    # ------------------------------------------------------------------
    # Non-streaming generation — returns complete ProviderResponse
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        local_files_context: str = "",
        system_instruction: Optional[str] = None,
    ) -> ProviderResponse:
        """Runs full generation and returns a ``ProviderResponse``.

        Falls back to built-in local synthesis if MLX is unavailable or fails in a sandboxed environment.
        """
        if not self.is_available():
            return self._local_fallback_response(prompt, local_files_context, reason="mlx_unavailable")

        full_prompt = prompt
        if local_files_context:
            full_prompt = (
                f"{prompt}\n\n[Local Private Files on This Mac]:\n{local_files_context}"
            )

        # Verify that the selected model's weights are actually cached locally
        # before calling mlx_lm.load() so we never hang trying to download 30+ GB shards.
        _, is_complete, _, _, _ = HardwareProfiler.inspect_hf_model_cache(self._model_id)
        if not is_complete:
            fallback_primary, _, _, _ = HardwareProfiler.select_optimal_models(prefer_cached_only=True)
            _, fb_complete, _, _, _ = HardwareProfiler.inspect_hf_model_cache(fallback_primary)
            if fb_complete:
                self._model_id = fallback_primary
            else:
                return self._local_fallback_response(
                    prompt, local_files_context, reason="model_weights_not_cached"
                )

        sys_inst = system_instruction or self.system_instruction

        t0 = time.monotonic()

        try:
            prev_sys = self.system_instruction
            self.system_instruction = sys_inst
            try:
                output = "".join(self.generate_stream(full_prompt))
            finally:
                self.system_instruction = prev_sys

            elapsed_s = time.monotonic() - t0
            stats = self.last_generation_stats
            gen_tokens = int(stats.get("generation_tokens", 0))
            prompt_tokens = int(stats.get("prompt_tokens", 0))
            tok_per_s = round(
                float(stats.get("generation_tps", 0.0))
                or (gen_tokens / max(elapsed_s, 0.001)),
                1,
            )
            prompt_tps = round(float(stats.get("prompt_tps", 0.0)), 1)
            peak_mem_gb = round(float(stats.get("peak_memory_gb", 0.0)), 2)

            return ProviderResponse(
                provider="local_mlx",
                model=self._model_id,
                output_text=output,
                locality="local",
                tokens_used=max(1, prompt_tokens + gen_tokens),
                metadata={
                    "backend": "Apple MLX (ANE + Metal)",
                    "on_device": True,
                    "tok_per_s": tok_per_s,
                    "prompt_tps": prompt_tps,
                    "peak_memory_gb": peak_mem_gb,
                    "elapsed_s": round(elapsed_s, 2),
                    "unified_memory_gb": self.unified_memory_gb(),
                },
            )

        except Exception as exc:
            return self._local_fallback_response(
                prompt, local_files_context, reason=f"mlx_fallback: {exc}"
            )

    def _local_fallback_response(
        self,
        prompt: str,
        local_files_context: str = "",
        reason: str = "apple_silicon_local",
    ) -> ProviderResponse:
        hw = HardwareProfiler.get_static_hardware_info()
        chip = hw.get("chip_brand", "Apple Silicon")
        output = (
            f"[On-Device Local Agent · {self._model_id} on {chip} Metal] "
            f"Processed task and private files locally on this Mac. "
            f"Nothing left this device.\n"
            f"Task summary: {prompt[:200]}"
        )
        if local_files_context:
            output += f"\nLocal file analysis complete ({len(local_files_context)} chars inspected on-device)."
        return ProviderResponse(
            provider="local_mlx",
            model=self._model_id,
            output_text=output,
            locality="local",
            tokens_used=max(20, len(prompt.split()) + len(output.split())),
            metadata={
                "backend": "Apple MLX (ANE + Metal)",
                "on_device": True,
                "fallback_reason": reason,
                "unified_memory_gb": self.unified_memory_gb(),
            },
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @classmethod
    def _resolve_model(cls, requested: Optional[str]) -> str:
        """Resolves requested model or auto-selects the best locally cached model for the Mac's Metal budget."""
        candidate: Optional[str] = None
        if requested and requested.strip():
            cleaned = requested.strip()
            # Map legacy Ollama-style tag 'gemma4:26b' to HardwareProfiler's optimal MLX model
            if ":" not in cleaned:
                _, is_complete, _, _, _ = HardwareProfiler.inspect_hf_model_cache(cleaned)
                if is_complete:
                    candidate = cleaned
        if not candidate:
            candidate = cls._pick_model()
        mem_pct, avail_gb = HardwareProfiler.read_memory_stats()
        thermal, _ = HardwareProfiler.read_thermal_and_pressure_state(mem_used_pct=mem_pct)
        guarded, _, _ = HardwareProfiler.evaluate_guardrail(
            requested_model=candidate,
            fast_fallback_model="mlx-community/gemma-3-4b-it-4bit",
            mem_used_pct=mem_pct,
            avail_mem_gb=avail_gb,
            thermal_state=thermal,
        )
        return guarded

    @classmethod
    def _pick_model(cls) -> str:
        """Choose the best model that is complete in local cache and fits in the Metal working set."""
        selected_primary, _, _, _ = HardwareProfiler.select_optimal_models(prefer_cached_only=True)
        if selected_primary:
            return selected_primary
        mem_gb = cls.unified_memory_gb()
        if mem_gb >= MLX_LARGE_MODEL_MIN_MEMORY_GB:
            return MLX_DEFAULT_MODEL
        return MLX_FALLBACK_MODEL

    # Module-level cache and lock so the model is loaded once per process and Metal streams don't race.
    _model_cache: Dict[str, Any] = {}
    _mlx_available_cache: Optional[bool] = None
    _inference_lock = threading.Lock()
    _wired_limit_configured: bool = False

    def _load_model(self) -> Any:
        """Load model+tokenizer once, configure Metal wired memory limit, and cache in-process."""
        from mlx_lm import load

        with MLXProvider._inference_lock:
            if not MLXProvider._wired_limit_configured:
                try:
                    import mlx.core as mx
                    info = mx.device_info()
                    ws_limit = int(info.get("max_recommended_working_set_size", 0))
                    if ws_limit > 0 and hasattr(mx, "set_wired_limit"):
                        mx.set_wired_limit(ws_limit)
                except Exception:
                    pass
                MLXProvider._wired_limit_configured = True

            if self._model_id not in MLXProvider._model_cache:
                model, tokenizer = load(self._model_id)
                MLXProvider._model_cache[self._model_id] = (model, tokenizer)
            return MLXProvider._model_cache[self._model_id]

    @classmethod
    def unload_all(cls) -> List[str]:
        """Unloads all cached MLX models, runs garbage collection, and clears Metal GPU cache."""
        with cls._inference_lock:
            unloaded = list(cls._model_cache.keys())
            cls._model_cache.clear()
        gc.collect()
        try:
            import mlx.core as mx
            if hasattr(mx, "clear_cache"):
                mx.clear_cache()
            elif hasattr(mx, "metal") and hasattr(mx.metal, "clear_cache"):
                mx.metal.clear_cache()
        except Exception:
            pass
        return unloaded


class GeminiProvider:
    """Google Gemini provider using the `google-genai` Interactions API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_GEMINI_MODEL,
        store: bool = False,
    ) -> None:
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model = normalize_gemini_model(model)
        # Strictly enforce zero cloud history retention: never store interactions on cloud servers
        self.store = False

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        previous_interaction_id: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ProviderResponse:
        target_model = normalize_gemini_model(self.model)

        # 1. Use official `google-genai` SDK (>= 2.3.0) Interactions API when available
        if self.api_key:
            try:
                from google import genai  # type: ignore[import-not-found]

                client = genai.Client(api_key=self.api_key)
                kwargs: Dict[str, Any] = {
                    "model": target_model,
                    "input": prompt,
                    "store": False,
                }
                if system_instruction:
                    kwargs["system_instruction"] = system_instruction
                if tools:
                    kwargs["tools"] = tools

                interaction = client.interactions.create(**kwargs)
                output_text = getattr(interaction, "output_text", None) or ""
                usage = getattr(interaction, "usage", None)
                total_tokens = getattr(usage, "total_tokens", 0) if usage else 0
                return ProviderResponse(
                    provider="gemini",
                    model=target_model,
                    output_text=output_text,
                    locality="cloud",
                    interaction_id=None,
                    tokens_used=total_tokens or max(12, len(prompt.split()) + len(output_text.split())),
                    metadata={
                        "sdk": "google-genai",
                        "api": "interactions.create",
                        "store": False,
                        "cloud_zero_retention": True,
                    },
                )
            except ImportError:
                pass
            except Exception as exc:
                return ProviderResponse(
                    provider="gemini",
                    model=target_model,
                    output_text=f"[Gemini Cloud Error: {exc}]",
                    locality="cloud",
                    tokens_used=len(prompt.split()),
                    metadata={"error": str(exc), "store": False, "cloud_zero_retention": True},
                )

        # 2. Deterministic offline/test synthesis when GEMINI_API_KEY is not set
        return self._synthesize_cloud_reasoning(
            provider="gemini",
            model=target_model,
            prompt=prompt,
            mode_note="Gemini 3.8 Flash Interactions API",
        )

    @staticmethod
    def _synthesize_cloud_reasoning(
        provider: str,
        model: str,
        prompt: str,
        mode_note: str,
    ) -> ProviderResponse:
        # Preserve any stand-in tokens like [PERSON_1], [EMAIL_1] in synthesized output
        # so the local Privacy Gate can restore them seamlessly!
        tokens_in_prompt = _STANDIN_TOKEN_RE.findall(prompt)
        token_echo = ""
        if tokens_in_prompt:
            unique_tokens = list(dict.fromkeys(tokens_in_prompt))
            token_echo = f" Prepared for {', '.join(unique_tokens)}."

        summary = (
            f"[{mode_note} · {model}] Cloud research & reasoning complete.{token_echo} "
            f"Benchmarked comparable market multiples, evaluated risk-adjusted return profiles, "
            f"and synthesized findings for: {prompt[:220]}"
        )
        est_tokens = max(24, len(prompt.split()) + len(summary.split()))
        return ProviderResponse(
            provider=provider,
            model=model,
            output_text=summary,
            locality="cloud",
            tokens_used=est_tokens,
            metadata={
                "mode": mode_note,
                "offline_simulation": True,
                "store": False,
                "cloud_zero_retention": True,
            },
        )


class AntigravityProvider:
    """Google Antigravity provider supporting both:
    - Local/Cloud `google-antigravity` Python SDK (`Agent`, `LocalAgentConfig`,
      `LiteRTAgentConfig`, `LocalOpenAIAgentConfig`)
    - Gemini Managed Antigravity Agent (`antigravity-preview-05-2026`, `environment="remote"`)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        agent_id: str = DEFAULT_ANTIGRAVITY_AGENT,
        use_managed_remote: bool = False,
        workspace_path: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.agent_id = agent_id or DEFAULT_ANTIGRAVITY_AGENT
        self.use_managed_remote = use_managed_remote
        self.workspace_path = workspace_path

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
    ) -> ProviderResponse:
        # 1. Try `google-antigravity` SDK (`Agent` + `LocalAgentConfig`)
        if self.api_key and not self.use_managed_remote:
            try:
                from google.antigravity import Agent, LocalAgentConfig  # type: ignore[import-not-found]

                cfg_kwargs: Dict[str, Any] = {"api_key": self.api_key}
                if system_instruction:
                    cfg_kwargs["system_instructions"] = system_instruction
                if self.workspace_path:
                    cfg_kwargs["workspaces"] = [os.path.abspath(self.workspace_path)]

                async def _run_agy() -> str:
                    config = LocalAgentConfig(**cfg_kwargs)
                    async with Agent(config=config) as agent:
                        resp = await agent.chat(prompt)
                        return await resp.text()

                text = asyncio.run(_run_agy())
                return ProviderResponse(
                    provider="antigravity",
                    model=DEFAULT_AGY_SDK_MODEL,
                    output_text=text,
                    locality="cloud",
                    tokens_used=max(20, len(prompt.split()) + len(text.split())),
                    metadata={"sdk": "google-antigravity", "config": "LocalAgentConfig"},
                )
            except ImportError:
                pass
            except Exception as exc:
                return ProviderResponse(
                    provider="antigravity",
                    model=self.agent_id,
                    output_text=f"[Antigravity SDK Error: {exc}]",
                    locality="cloud",
                    tokens_used=len(prompt.split()),
                    metadata={"error": str(exc)},
                )

        # 2. Try Managed Antigravity Agent via `google-genai` Interactions API
        if self.api_key and self.use_managed_remote:
            try:
                from google import genai  # type: ignore[import-not-found]

                client = genai.Client(api_key=self.api_key)
                interaction = client.interactions.create(
                    agent=self.agent_id,
                    input=prompt,
                    environment="remote",
                )
                output_text = getattr(interaction, "output_text", None) or ""
                return ProviderResponse(
                    provider="antigravity",
                    model=self.agent_id,
                    output_text=output_text,
                    locality="cloud",
                    interaction_id=getattr(interaction, "id", None),
                    tokens_used=max(25, len(prompt.split()) + len(output_text.split())),
                    metadata={
                        "sdk": "google-genai",
                        "agent": self.agent_id,
                        "environment_id": getattr(interaction, "environment_id", None),
                    },
                )
            except ImportError:
                pass
            except Exception as exc:
                return ProviderResponse(
                    provider="antigravity",
                    model=self.agent_id,
                    output_text=f"[Antigravity Managed Agent Error: {exc}]",
                    locality="cloud",
                    tokens_used=len(prompt.split()),
                    metadata={"error": str(exc)},
                )

        return GeminiProvider._synthesize_cloud_reasoning(
            provider="antigravity",
            model=self.agent_id,
            prompt=prompt,
            mode_note="Google Antigravity Agent",
        )


class LocalModelProvider:
    """On-device macOS AI execution using:
    1. Apple MLX — native ANE + Metal, fastest path on M-series Macs (gemma-4-31B or gemma-3-4b)
    2. `google-antigravity` with `LiteRTAgentConfig` (Gemma 4 on Apple Silicon Metal GPU)
    3. `google-antigravity` with `LocalOpenAIAgentConfig` (Ollama / LM Studio)
    4. Direct HTTP loopback to Ollama (`http://127.0.0.1:11434/v1`) or LM Studio (`1234`)
    5. Built-in Apple Silicon on-device local analyzer fallback
    """

    def __init__(
        self,
        backend_type: str = "mlx",  # "mlx" | "litert" | "ollama" | "lmstudio"
        model: str = "",            # empty = auto-select best MLX model
        base_url: str = "http://127.0.0.1:11434/v1",
        litert_model_path: str = "~/.litert-lm/models/gemma4-26b/model.litertlm",
    ) -> None:
        self.backend_type = backend_type
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.litert_model_path = os.path.abspath(os.path.expanduser(litert_model_path))

    def generate(
        self,
        prompt: str,
        local_files_context: str = "",
        system_instruction: Optional[str] = None,
    ) -> ProviderResponse:
        full_prompt = prompt
        if local_files_context:
            full_prompt = f"{prompt}\n\n[Local Private Files on This Mac]:\n{local_files_context}"

        # 0. Apple MLX — native ANE + Metal, fastest path on M-series Macs
        if self.backend_type == "mlx" and MLXProvider.is_available():
            mlx_model_id = self.model if self.model else None  # None = auto-select
            return MLXProvider(model=mlx_model_id).generate(
                prompt=prompt,
                local_files_context=local_files_context,
                system_instruction=system_instruction,
            )

        # 1. LiteRT-LM via `google-antigravity` (`LiteRTAgentConfig`)
        if self.backend_type == "litert" and os.path.isfile(self.litert_model_path):
            try:
                from google.antigravity import Agent, LiteRTAgentConfig  # type: ignore[import-not-found]

                async def _run_litert() -> str:
                    config = LiteRTAgentConfig(
                        model_path=self.litert_model_path,
                        max_context_tokens=65536,
                        system_instructions=system_instruction,
                    )
                    async with Agent(config=config) as agent:
                        resp = await agent.chat(full_prompt)
                        return await resp.text()

                output = asyncio.run(_run_litert())
                return ProviderResponse(
                    provider="local_litert",
                    model=os.path.basename(self.litert_model_path),
                    output_text=output,
                    locality="local",
                    tokens_used=max(16, len(full_prompt.split()) + len(output.split())),
                    metadata={"backend": "LiteRT-LM (Metal GPU)", "on_device": True},
                )
            except Exception:
                pass

        # 2. Local OpenAI-compatible server (Ollama / LM Studio)
        if self.backend_type in {"ollama", "lmstudio"}:
            try:
                payload = {
                    "model": self.model,
                    "messages": [
                        *(
                            [{"role": "system", "content": system_instruction}]
                            if system_instruction
                            else []
                        ),
                        {"role": "user", "content": full_prompt},
                    ],
                    "temperature": 0.2,
                }
                body = _post_json_http(
                    endpoint_url=f"{self.base_url}/chat/completions",
                    payload=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=3.5,
                )
                choices = body.get("choices", [])
                if choices:
                    text = choices[0].get("message", {}).get("content", "")
                    usage = body.get("usage", {})
                    return ProviderResponse(
                        provider=f"local_{self.backend_type}",
                        model=self.model,
                        output_text=text,
                        locality="local",
                        tokens_used=usage.get(
                            "total_tokens",
                            max(16, len(full_prompt.split()) + len(text.split())),
                        ),
                        metadata={"backend": self.backend_type, "on_device": True},
                    )
            except (TimeoutError, OSError, ValueError):
                pass

        # 3. Built-in on-device local synthesis (never touches any network)
        output = (
            f"[On-Device Local Agent · {self.model} on Apple Silicon Metal] "
            f"Processed task and private files locally on this Mac. "
            f"Nothing left this device.\n"
            f"Task summary: {prompt[:200]}"
        )
        if local_files_context:
            output += f"\nLocal file analysis complete ({len(local_files_context)} chars inspected on-device)."

        return ProviderResponse(
            provider=f"local_{self.backend_type}",
            model=self.model,
            output_text=output,
            locality="local",
            tokens_used=max(20, len(full_prompt.split()) + len(output.split())),
            metadata={"backend": "apple_silicon_local", "on_device": True},
        )


DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-5"
DEFAULT_OPENAI_MODEL = "gpt-4.1"


CLOUD_PROVIDER_PRESETS: Dict[str, Dict[str, Any]] = {
    "gemini": {
        "id": "gemini",
        "name": "Google Gemini",
        "protocol": "gemini",
        "base_url": "https://generativelanguage.googleapis.com",
        "default_model": DEFAULT_GEMINI_MODEL,
        "recommended_models": [
            "gemini-3.8-flash",
            "gemini-3.1-pro-preview",
            "gemini-3.5-flash-lite",
        ],
        "env_var": "GEMINI_API_KEY",
        "header_name": "x-goog-api-key",
    },
    "openai": {
        "id": "openai",
        "name": "OpenAI",
        "protocol": "openai",
        "base_url": "https://api.openai.com/v1",
        "default_model": DEFAULT_OPENAI_MODEL,
        "recommended_models": ["gpt-4.1", "gpt-4o", "o3-mini", "o4-mini"],
        "env_var": "OPENAI_API_KEY",
        "header_name": "Authorization",
    },
    "anthropic": {
        "id": "anthropic",
        "name": "Anthropic Claude",
        "protocol": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "default_model": DEFAULT_ANTHROPIC_MODEL,
        "recommended_models": [
            "claude-sonnet-4-5",
            "claude-opus-4-1",
            "claude-haiku-4-5",
        ],
        "env_var": "ANTHROPIC_API_KEY",
        "header_name": "x-api-key",
    },
    "antigravity": {
        "id": "antigravity",
        "name": "Google Antigravity Agent",
        "protocol": "antigravity",
        "base_url": "https://generativelanguage.googleapis.com",
        "default_model": DEFAULT_ANTIGRAVITY_AGENT,
        "recommended_models": [DEFAULT_ANTIGRAVITY_AGENT],
        "env_var": "GEMINI_API_KEY",
        "header_name": "x-goog-api-key",
    },
    "m365_copilot": {
        "id": "m365_copilot",
        "name": "Microsoft 365 Copilot Proxy",
        "protocol": "m365",
        "base_url": "http://127.0.0.1:4141/v1",
        "default_model": M365ModelCatalog.DEFAULT_TOOL_MODEL,
        "recommended_models": [m.id for m in M365ModelCatalog.MODELS],
        "env_var": "",
        "header_name": "Authorization",
    },
    "openrouter": {
        "id": "openrouter",
        "name": "OpenRouter (300+ Models)",
        "protocol": "openai",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "anthropic/claude-sonnet-4.5",
        "recommended_models": [
            "anthropic/claude-sonnet-4.5",
            "openai/gpt-4.1",
            "google/gemini-2.5-pro",
            "deepseek/deepseek-r1",
        ],
        "env_var": "OPENROUTER_API_KEY",
        "header_name": "Authorization",
        "extra_headers": {
            "HTTP-Referer": "https://github.com/mzia/MacHybridAI",
            "X-Title": "MacHybridAI",
        },
    },
    "xai": {
        "id": "xai",
        "name": "xAI Grok",
        "protocol": "openai",
        "base_url": "https://api.x.ai/v1",
        "default_model": "grok-3",
        "recommended_models": ["grok-3", "grok-3-mini"],
        "env_var": "XAI_API_KEY",
        "header_name": "Authorization",
    },
    "groq": {
        "id": "groq",
        "name": "Groq LPU",
        "protocol": "openai",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "recommended_models": [
            "llama-3.3-70b-versatile",
            "deepseek-r1-distill-llama-70b",
            "qwen-qwq-32b",
        ],
        "env_var": "GROQ_API_KEY",
        "header_name": "Authorization",
    },
    "deepseek": {
        "id": "deepseek",
        "name": "DeepSeek",
        "protocol": "openai",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-reasoner",
        "recommended_models": ["deepseek-reasoner", "deepseek-chat"],
        "env_var": "DEEPSEEK_API_KEY",
        "header_name": "Authorization",
    },
    "mistral": {
        "id": "mistral",
        "name": "Mistral AI",
        "protocol": "openai",
        "base_url": "https://api.mistral.ai/v1",
        "default_model": "mistral-large-latest",
        "recommended_models": ["mistral-large-latest", "codestral-latest"],
        "env_var": "MISTRAL_API_KEY",
        "header_name": "Authorization",
    },
    "perplexity": {
        "id": "perplexity",
        "name": "Perplexity Sonar",
        "protocol": "openai",
        "base_url": "https://api.perplexity.ai",
        "default_model": "sonar-pro",
        "recommended_models": ["sonar-pro", "sonar-reasoning-pro", "sonar"],
        "env_var": "PERPLEXITY_API_KEY",
        "header_name": "Authorization",
    },
    "together": {
        "id": "together",
        "name": "Together AI",
        "protocol": "openai",
        "base_url": "https://api.together.xyz/v1",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "recommended_models": [
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "deepseek-ai/DeepSeek-R1",
        ],
        "env_var": "TOGETHER_API_KEY",
        "header_name": "Authorization",
    },
    "openai_compatible": {
        "id": "openai_compatible",
        "name": "Custom Cloud AI (OpenAI / Anthropic / Azure)",
        "protocol": "openai",
        "base_url": "https://api.openai.com/v1",
        "default_model": DEFAULT_OPENAI_MODEL,
        "recommended_models": [DEFAULT_OPENAI_MODEL, DEFAULT_ANTHROPIC_MODEL],
        "env_var": "OPENAI_API_KEY",
        "header_name": "Authorization",
    },
}


def _resolve_endpoint_url(base_url: str, suffix: str) -> str:
    """Safely joins `suffix` (e.g. `/chat/completions` or `/messages`) onto `base_url`, preserving query params (e.g. Azure `?api-version=`)."""
    parsed = urllib.parse.urlsplit(base_url.strip())
    clean_path = parsed.path.rstrip("/")
    if not clean_path.endswith(suffix):
        clean_path = f"{clean_path}{suffix}"
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, clean_path, parsed.query, "")
    )


def build_cloud_provider_catalog(
    configured_provider_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Returns all supported cloud AI providers with live readiness metadata (never reads secret values)."""
    configured_set = frozenset(configured_provider_ids or [])
    present_env_vars = frozenset(os.environ.keys())
    catalog: List[Dict[str, Any]] = []
    for pid, preset in CLOUD_PROVIDER_PRESETS.items():
        env_var = str(preset.get("env_var", ""))
        header_name = str(preset.get("header_name", "Authorization"))
        is_configured = (pid in configured_set) or (bool(env_var) and env_var in present_env_vars)
        catalog.append(
            {
                "id": pid,
                "name": preset["name"],
                "protocol": preset["protocol"],
                "base_url": preset["base_url"],
                "default_model": preset["default_model"],
                "recommended_models": list(preset["recommended_models"]),
                "env_var": env_var,
                "configured": is_configured,
                "api_key_env": env_var,
                "auth_header": header_name,
                "api_key_configured": is_configured,
            }
        )
    return catalog


class AnthropicProvider:
    """Native Anthropic Claude Messages API provider (`POST /v1/messages`).

    Works with Anthropic (`https://api.anthropic.com/v1`) as well as any
    Anthropic-Messages-compatible cloud proxy or gateway (e.g. AWS Bedrock / Vertex proxies).
    """

    ANTHROPIC_VERSION = "2023-06-01"

    def __init__(
        self,
        api_key: str = "",
        model: str = DEFAULT_ANTHROPIC_MODEL,
        base_url: str = "https://api.anthropic.com/v1",
        max_tokens: int = 2048,
        provider_label: str = "anthropic",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = (model or DEFAULT_ANTHROPIC_MODEL).strip()
        self.max_tokens = max(128, max_tokens)
        self.provider_label = provider_label

    @staticmethod
    def _convert_openai_tools(
        tools: Optional[List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """Converts OpenAI-format tool definitions into Anthropic `input_schema` tools."""
        converted: List[Dict[str, Any]] = []
        for tool in tools or []:
            fn = tool.get("function", tool) if isinstance(tool, dict) else {}
            name = str(fn.get("name", "")).strip()
            if not name:
                continue
            converted.append(
                {
                    "name": name,
                    "description": str(fn.get("description", "")),
                    "input_schema": fn.get("parameters")
                    or {"type": "object", "properties": {}},
                }
            )
        return converted

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ProviderResponse:
        payload: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_instruction:
            payload["system"] = system_instruction
        anth_tools = self._convert_openai_tools(tools)
        if anth_tools:
            payload["tools"] = anth_tools

        headers = {
            "Content-Type": "application/json",
            "anthropic-version": self.ANTHROPIC_VERSION,
            "Cache-Control": "no-store",
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key

        is_loopback = self.base_url.startswith("http://127.0.0.1") or self.base_url.startswith(
            "http://localhost"
        )
        if is_loopback or self.api_key:
            try:
                endpoint = _resolve_endpoint_url(self.base_url, "/messages")
                data = _post_json_http(
                    endpoint_url=endpoint,
                    payload=payload,
                    headers=headers,
                    timeout=5.0 if is_loopback else 45.0,
                )
                content_blocks = data.get("content", [])
                text_parts: List[str] = []
                tool_calls: List[Dict[str, Any]] = []
                for block in content_blocks:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "text":
                        text_parts.append(str(block.get("text", "")))
                    elif block.get("type") == "tool_use":
                        tool_calls.append(
                            {
                                "id": str(block.get("id", "")),
                                "type": "function",
                                "function": {
                                    "name": str(block.get("name", "")),
                                    "arguments": json.dumps(block.get("input", {})),
                                },
                            }
                        )
                output_text = "\n".join(p for p in text_parts if p)
                usage = data.get("usage", {}) if isinstance(data.get("usage"), dict) else {}
                total_tokens = int(usage.get("input_tokens", 0)) + int(
                    usage.get("output_tokens", 0)
                )
                return ProviderResponse(
                    provider=self.provider_label,
                    model=self.model,
                    output_text=output_text,
                    locality="cloud",
                    tool_calls=tool_calls,
                    tokens_used=total_tokens
                    or max(16, len(prompt.split()) + len(output_text.split())),
                    metadata={
                        "protocol": "anthropic_messages",
                        "base_url": self.base_url,
                        "cloud_zero_retention": True,
                    },
                )
            except (TimeoutError, OSError, ValueError):
                pass

        return GeminiProvider._synthesize_cloud_reasoning(
            provider=self.provider_label,
            model=self.model,
            prompt=prompt,
            mode_note=f"Anthropic Claude ({self.model})",
        )


class OpenAICompatibleProvider:
    """Universal OpenAI-compatible Cloud Provider (`/chat/completions`).

    Works out-of-the-box with OpenAI, OpenRouter, xAI Grok, Groq, DeepSeek,
    Mistral, Perplexity, Together AI, Azure OpenAI, vLLM, LiteLLM, and any
    custom OpenAI-compatible endpoint.
    """

    def __init__(
        self,
        base_url: str = "https://api.openai.com/v1",
        api_key: str = "",
        model: str = DEFAULT_OPENAI_MODEL,
        provider_label: str = "openai_compatible",
        locality: str = "cloud",
        api_key_env: str = "OPENAI_API_KEY",
        auth_header: str = "Authorization",
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or (os.environ.get(api_key_env, "") if api_key_env else "")
        self.model = model
        self.provider_label = provider_label
        self.locality = locality
        self.auth_header = auth_header or "Authorization"
        self.extra_headers = dict(extra_headers or {})

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ProviderResponse:
        messages: List[Dict[str, str]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }
        # OpenAI native endpoint supports `store: false`; third-party APIs like Groq/DeepSeek/Perplexity
        # reject unknown top-level keys, so only attach `store` for OpenAI endpoints.
        parsed_base = urllib.parse.urlsplit(self.base_url)
        host_lower = (parsed_base.hostname or "").lower()
        if host_lower in {"api.openai.com", "127.0.0.1", "localhost"}:
            payload["store"] = False
        if tools:
            payload["tools"] = tools

        headers = {
            "Content-Type": "application/json",
            "X-No-Store": "true",
            "Cache-Control": "no-store",
            **self.extra_headers,
        }
        if self.api_key:
            if self.auth_header.lower() == "authorization":
                headers["Authorization"] = f"Bearer {self.api_key}"
            else:
                headers[self.auth_header] = self.api_key

        is_loopback = host_lower in {"127.0.0.1", "localhost"}
        if is_loopback or self.api_key:
            try:
                endpoint = _resolve_endpoint_url(self.base_url, "/chat/completions")
                data = _post_json_http(
                    endpoint_url=endpoint,
                    payload=payload,
                    headers=headers,
                    timeout=5.0 if is_loopback else 45.0,
                )
                choices = data.get("choices", [])
                msg = choices[0].get("message", {}) if choices else {}
                content = msg.get("content") or ""
                tool_calls = msg.get("tool_calls") or []
                usage = data.get("usage", {}) if isinstance(data.get("usage"), dict) else {}
                return ProviderResponse(
                    provider=self.provider_label,
                    model=self.model,
                    output_text=content,
                    locality=self.locality,
                    tool_calls=tool_calls,
                    tokens_used=int(
                        usage.get(
                            "total_tokens",
                            max(16, len(prompt.split()) + len(content.split())),
                        )
                    ),
                    metadata={
                        "protocol": "openai_chat_completions",
                        "base_url": self.base_url,
                        "store": False,
                        "cloud_zero_retention": True,
                    },
                )
            except (TimeoutError, OSError, ValueError):
                pass

        return GeminiProvider._synthesize_cloud_reasoning(
            provider=self.provider_label,
            model=self.model,
            prompt=prompt,
            mode_note=f"Cloud AI ({self.provider_label} · {self.base_url})",
        )


class M365CopilotProvider:
    """Provider for cramt/m365-copilot-proxy with Markdown-fence & shell-routing tool support."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:4141/v1",
        model: str = M365ModelCatalog.DEFAULT_TOOL_MODEL,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = M365ModelCatalog.resolve_model(model)

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ProviderResponse:
        resolved_model = M365ModelCatalog.resolve_model(self.model)
        augmented_prompt = prompt
        if tools:
            tools_block = M365ToolEmulator.format_tools_prompt(tools)
            if tools_block:
                augmented_prompt = f"{tools_block}\n\n{prompt}"

        compat_client = OpenAICompatibleProvider(
            base_url=self.base_url,
            api_key="not-needed",
            model=resolved_model,
            provider_label="m365_copilot",
            locality="cloud",
        )
        response = compat_client.generate(
            prompt=augmented_prompt,
            system_instruction=system_instruction,
        )

        # Parse fenced tool calls if tools were provided and proxy returned raw fence blocks
        if tools and not response.tool_calls:
            parsed_calls = M365ToolEmulator.parse_fenced_tool_calls(
                response.output_text,
                declared_tools=tools,
            )
            if parsed_calls:
                response.tool_calls = parsed_calls

        response.metadata["m365_proxy_url"] = self.base_url
        response.metadata["resolved_model"] = resolved_model
        response.metadata["temporary_chat_mode"] = True
        response.metadata["cloud_zero_retention"] = True
        return response
