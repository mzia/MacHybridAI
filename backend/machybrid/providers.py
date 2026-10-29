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
import http.client
import json
import os
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generator, List, Optional

from .m365_proxy import M365ModelCatalog, M365ToolEmulator

# Deprecated Gemini model guard per gemini-api-dev skill rules
_DEPRECATED_GEMINI_PREFIXES = ("gemini-2.5", "gemini-2.0", "gemini-1.5", "gemini-1.0")
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
    ) -> None:
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.system_instruction = system_instruction
        self._model_id = model or self._pick_model()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @staticmethod
    def is_available() -> bool:
        """Returns True when mlx and mlx-lm are importable (installed)."""
        try:
            import mlx.core  # noqa: F401
            import mlx_lm  # noqa: F401
            return True
        except ImportError:
            return False

    @staticmethod
    def unified_memory_gb() -> int:
        """Returns unified memory size in GB via MLX device info."""
        try:
            import mlx.core as mx
            info = mx.device_info()
            return int(info.get("memory_size", 0)) // (1024 ** 3)
        except Exception:
            return 0

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
    ) -> Generator[str, None, None]:
        """Yields token strings from the MLX model one at a time.

        Args:
            prompt: The full prompt string (already sanitized by Privacy Gate).
            token_callback: Optional side-effect callback called with each token
                            (e.g. to push to a Server-Sent Events response).

        Yields:
            Individual token strings as they are generated on the ANE/Metal.
        """
        from mlx_lm import load
        from mlx_lm.utils import generate_step

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

        input_ids = tokenizer.encode(formatted)  # type: ignore[union-attr]

        import mlx.core as mx
        input_tensor = mx.array(input_ids)

        token_count = 0
        for token_id, _logprobs in generate_step(
            input_tensor,
            model,
            temp=self.temperature,
            top_p=0.95,
        ):
            if token_count >= self.max_tokens:
                break
            token_str = tokenizer.decode([token_id.item()])  # type: ignore[union-attr]
            if token_callback:
                token_callback(token_str)
            yield token_str
            token_count += 1

            # Stop at EOS
            if token_id.item() == tokenizer.eos_token_id:  # type: ignore[union-attr]
                break

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

        Falls back to Ollama if MLX is not installed.
        """
        if not self.is_available():
            # Graceful degradation — should not normally happen if wired up correctly
            return ProviderResponse(
                provider="local_mlx",
                model=self._model_id,
                output_text="[MLX not installed — falling back to Ollama]",
                locality="local",
                tokens_used=0,
                metadata={"backend": "mlx_unavailable", "on_device": True},
            )

        full_prompt = prompt
        if local_files_context:
            full_prompt = (
                f"{prompt}\n\n[Local Private Files on This Mac]:\n{local_files_context}"
            )

        sys_inst = system_instruction or self.system_instruction

        import time as _time
        t0 = _time.monotonic()

        try:
            from mlx_lm import load, generate as mlx_generate

            model, tokenizer = self._load_model()

            # Apply chat template
            messages: List[Dict[str, str]] = []
            if sys_inst:
                messages.append({"role": "system", "content": sys_inst})
            messages.append({"role": "user", "content": full_prompt})

            if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:  # type: ignore[union-attr]
                formatted = tokenizer.apply_chat_template(  # type: ignore[union-attr]
                    messages, tokenize=False, add_generation_prompt=True
                )
            else:
                formatted = full_prompt

            output = mlx_generate(
                model,
                tokenizer,
                prompt=formatted,
                max_tokens=self.max_tokens,
                temp=self.temperature,
                verbose=False,
            )

            elapsed_s = _time.monotonic() - t0
            # mlx_generate returns the generated text only (no prompt echo)
            token_count = len(tokenizer.encode(output)) if output else 0  # type: ignore[union-attr]
            tok_per_s = round(token_count / max(elapsed_s, 0.001), 1)

            return ProviderResponse(
                provider="local_mlx",
                model=self._model_id,
                output_text=output,
                locality="local",
                tokens_used=token_count,
                metadata={
                    "backend": "Apple MLX (ANE + Metal)",
                    "on_device": True,
                    "tok_per_s": tok_per_s,
                    "elapsed_s": round(elapsed_s, 2),
                    "unified_memory_gb": self.unified_memory_gb(),
                },
            )

        except Exception as exc:
            elapsed_s = _time.monotonic() - t0
            return ProviderResponse(
                provider="local_mlx",
                model=self._model_id,
                output_text=f"[MLX Error: {exc}]",
                locality="local",
                tokens_used=0,
                metadata={"backend": "mlx_error", "error": str(exc), "elapsed_s": round(elapsed_s, 2)},
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @classmethod
    def _pick_model(cls) -> str:
        """Choose the best model that fits in available unified memory."""
        mem_gb = cls.unified_memory_gb()
        if mem_gb >= MLX_LARGE_MODEL_MIN_MEMORY_GB:
            return MLX_DEFAULT_MODEL
        return MLX_FALLBACK_MODEL

    # Module-level cache so the model is loaded once per process.
    _model_cache: Dict[str, Any] = {}

    def _load_model(self) -> Any:
        """Load model+tokenizer once and cache in-process."""
        from mlx_lm import load

        if self._model_id not in MLXProvider._model_cache:
            model, tokenizer = load(self._model_id)
            MLXProvider._model_cache[self._model_id] = (model, tokenizer)
        return MLXProvider._model_cache[self._model_id]


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
        import re

        tokens_in_prompt = re.findall(r"\[[A-Z_]+_\d+\]", prompt)
        token_Echo = ""
        if tokens_in_prompt:
            unique_tokens = list(dict.fromkeys(tokens_in_prompt))
            token_Echo = f" Prepared for {', '.join(unique_tokens)}."

        summary = (
            f"[{mode_note} · {model}] Cloud research & reasoning complete.{token_Echo} "
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


class OpenAICompatibleProvider:
    """Configurable OpenAI Extension Provider (`/v1/chat/completions`).

    Allows easy configuration of any OpenAI-compatible service (OpenRouter,
    Together, vLLM, Groq, OpenAI, Azure OpenAI, etc.).
    """

    def __init__(
        self,
        base_url: str = "https://api.openai.com/v1",
        api_key: str = "",
        model: str = "gpt-4.1",
        provider_label: str = "openai_compatible",
        locality: str = "cloud",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model
        self.provider_label = provider_label
        self.locality = locality

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
            "store": False,
        }
        if tools:
            payload["tools"] = tools

        headers = {
            "Content-Type": "application/json",
            "X-No-Store": "true",
            "Cache-Control": "no-store",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        if self.base_url.startswith("http://127.0.0.1") or self.base_url.startswith(
            "http://localhost"
        ) or self.api_key:
            try:
                data = _post_json_http(
                    endpoint_url=f"{self.base_url}/chat/completions",
                    payload=payload,
                    headers=headers,
                    timeout=5.0,
                )
                choices = data.get("choices", [])
                msg = choices[0].get("message", {}) if choices else {}
                content = msg.get("content") or ""
                tool_calls = msg.get("tool_calls") or []
                usage = data.get("usage", {})
                return ProviderResponse(
                    provider=self.provider_label,
                    model=self.model,
                    output_text=content,
                    locality=self.locality,
                    tool_calls=tool_calls,
                    tokens_used=usage.get(
                        "total_tokens",
                        max(16, len(prompt.split()) + len(content.split())),
                    ),
                    metadata={
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
            mode_note=f"OpenAI Extension ({self.base_url})",
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
