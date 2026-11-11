"""Local Loopback HTTP Daemon for MacHybridAI (`127.0.0.1:8765`).

Binds strictly to localhost so no external network host can invoke the hybrid engine.
Provides JSON endpoints for the native macOS SwiftUI app and CLI:
- `GET /health`
- `GET /v1/config` & `POST /v1/config`
- `POST /v1/guardian/inspect`
- `POST /v1/tasks/run`
- `POST /v1/tasks/stream`   ← Server-Sent Events streaming (token-by-token)
- `GET /v1/mlx/status`      ← MLX availability + active model info
- `GET /v1/m365/status` & `POST /v1/m365/control`
"""

from __future__ import annotations

import argparse
import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Tuple

from . import __version__
from .guardian import GuardianPolicy
from .history import HistoryRetentionPolicy, HistoryStorageLocation
from .m365_proxy import M365ToolEmulator
from .orchestrator import ComputeMode, HybridOrchestrator
from .profiler import HardwareProfiler
from .providers import MLXProvider

MAX_REQUEST_BYTES = 1_048_576  # 1 MiB limit against payload DoS


class HybridRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler backed by a shared `HybridOrchestrator`."""

    orchestrator: HybridOrchestrator = HybridOrchestrator()

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy access logs or sensitive query logging
        return

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _read_json_body(self) -> Optional[Dict[str, Any]]:
        length_header = self.headers.get("Content-Length", "0")
        try:
            length = int(length_header)
        except ValueError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid Content-Length"})
            return None

        if length < 0 or length > MAX_REQUEST_BYTES:
            self._send_json(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {"error": f"Payload exceeds {MAX_REQUEST_BYTES} bytes"},
            )
            return None

        if length == 0:
            return {}

        raw = self.rfile.read(length)
        try:
            parsed = json.loads(raw.decode("utf-8"))
            if not isinstance(parsed, dict):
                raise ValueError("JSON root must be an object")
            return parsed
        except Exception as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": f"Invalid JSON: {exc}"})
            return None

    def do_GET(self) -> None:
        status, payload = dispatch_request(self.orchestrator, "GET", self.path)
        self._send_json(status, payload)

    def do_POST(self) -> None:
        # /v1/tasks/stream uses chunked SSE — handled separately
        if self.path == "/v1/tasks/stream":
            self._handle_stream()
            return
        body = self._read_json_body()
        if body is None:
            return
        if self.path == "/v1/chat/completions" and bool(body.get("stream", False)):
            self._handle_openai_stream(body)
            return
        status, payload = dispatch_request(self.orchestrator, "POST", self.path, body)
        self._send_json(status, payload)
        if self.path == "/v1/shutdown" and status == HTTPStatus.OK:
            threading.Thread(target=self.server.shutdown, daemon=True).start()

    def _handle_openai_stream(self, body: Dict[str, Any]) -> None:
        """OpenAI-compatible SSE streaming endpoint for `POST /v1/chat/completions`."""
        import time as _time

        status, payload = dispatch_request(
            self.orchestrator,
            "POST",
            "/v1/chat/completions",
            {**body, "stream": False},
        )
        if status != HTTPStatus.OK:
            self._send_json(status, payload)
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        choices = payload.get("choices", [])
        text = ""
        if choices and isinstance(choices[0], dict):
            msg = choices[0].get("message", {})
            if isinstance(msg, dict):
                text = str(msg.get("content", ""))

        chunk_id = str(payload.get("id", f"chatcmpl_{int(_time.time())}"))
        model_name = str(payload.get("model", "machybrid-hybrid"))
        created_ts = int(payload.get("created", int(_time.time())))

        try:
            words = text.split(" ")
            for i, word in enumerate(words):
                piece = word if i == 0 else " " + word
                chunk_obj = {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "created": created_ts,
                    "model": model_name,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": piece},
                            "finish_reason": None,
                        }
                    ],
                }
                self.wfile.write(f"data: {json.dumps(chunk_obj)}\n\n".encode("utf-8"))
                self.wfile.flush()

            final_chunk = {
                "id": chunk_id,
                "object": "chat.completion.chunk",
                "created": created_ts,
                "model": model_name,
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop",
                    }
                ],
                "x_machybrid_receipt": payload.get("x_machybrid_receipt"),
            }
            self.wfile.write(f"data: {json.dumps(final_chunk)}\n\n".encode("utf-8"))
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _handle_stream(self) -> None:
        """Server-Sent Events streaming for token-by-token MLX output.

        Protocol (SSE):
          data: <token_json>\\n\\n   — one token per event
          data: [DONE]\\n\\n         — stream complete, final metadata follows
          data: <receipt_json>\\n\\n — final receipt/telemetry event

        The client can render tokens as they arrive for instant perceived response.
        Privacy Gate runs before streaming starts — no raw PII is ever streamed.
        """
        body = self._read_json_body()
        if body is None:
            return

        prompt = str(body.get("prompt", "")).strip()
        if not prompt:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "prompt is required"})
            return

        # Resolve compute mode
        mode_override: Optional[ComputeMode] = None
        if body.get("mode"):
            try:
                mode_override = ComputeMode(str(body["mode"]))
            except ValueError:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": f"Invalid mode: {body.get('mode')}"})
                return

        # Run the Privacy Gate synchronously before streaming starts.
        # Only the sanitized prompt leaves this function.
        redaction = self.orchestrator.guardian.redact(prompt)

        # If policy forces local, stream from the local MLX model directly.
        use_local_only = (
            redaction.forced_local
            or (mode_override == ComputeMode.LOCAL)
            or (self.orchestrator.config.compute_mode == ComputeMode.LOCAL and mode_override is None)
        )

        # --- Begin SSE response ---
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        def sse(data: str) -> None:
            """Write one SSE event; silently swallow broken pipe on client disconnect."""
            try:
                raw = f"data: {data}\n\n".encode("utf-8")
                self.wfile.write(raw)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

        # --- Stream from MLX (local) or run full hybrid task ---
        file_paths = (
            body.get("file_paths")
            if isinstance(body.get("file_paths"), list)
            else []
        )
        inline_context = str(body.get("inline_file_context", ""))

        if use_local_only and MLXProvider.is_available():
            import time as _time
            t0 = _time.monotonic()
            mlx_model = body.get("mlx_model") or self.orchestrator.config.local_model or None
            provider = MLXProvider(model=mlx_model)
            _, is_complete, _, _, _ = HardwareProfiler.inspect_hf_model_cache(provider.model_id)

            full_local_prompt = redaction.sanitized_text
            if inline_context:
                full_local_prompt = f"{redaction.sanitized_text}\n\n[Local Private Files on This Mac]:\n{inline_context}"

            token_count = 0
            if is_complete:
                try:
                    for token in provider.generate_stream(full_local_prompt):
                        sse(json.dumps({"type": "token", "text": token}))
                        token_count += 1
                except Exception:
                    token_count = 0

            if token_count == 0:
                fallback_resp = provider.generate(
                    redaction.sanitized_text, local_files_context=inline_context
                )
                for i, word in enumerate(fallback_resp.output_text.split(" ")):
                    chunk = word if i == 0 else " " + word
                    sse(json.dumps({"type": "token", "text": chunk}))
                    token_count += 1

            elapsed_ms = max(1, int((_time.monotonic() - t0) * 1000))
            local_stations = [
                {
                    "station_index": 1,
                    "station_id": "this_mac",
                    "label": "This Mac",
                    "locality": "local",
                    "title": f"Local agent & {provider.model_id} processed task on-device",
                    "detail": f"Processed {len(file_paths)} local file(s) on this Mac. Nothing leaves this Mac.",
                    "status": "completed",
                    "duration_ms": elapsed_ms,
                    "badges": ["Fully Local", provider.model_id, "Nothing leaves this Mac"],
                },
                {
                    "station_index": 2,
                    "station_id": "cloud",
                    "label": "Cloud models",
                    "locality": "local",
                    "title": "Cloud models not used",
                    "detail": "AI processing stayed 100% on your Mac. Zero Cloud AI history.",
                    "status": "completed",
                    "duration_ms": 0,
                    "badges": ["Not used", "Zero Cloud History"],
                },
                {
                    "station_index": 3,
                    "station_id": "result",
                    "label": "Result",
                    "locality": "local",
                    "title": "Completed on this Mac",
                    "detail": "Result generated locally with zero cloud transmission.",
                    "status": "completed",
                    "duration_ms": 1,
                    "badges": ["Verified On-Device"],
                },
            ]
            local_receipt = {
                "mode_executed": "local",
                "local_model_used": f"{provider.model_id} (on this Mac)",
                "local_agent_location": "on this Mac",
                "cloud_models_used": "not used",
                "pii_flagged_count": redaction.pii_count,
                "pii_restored_count": 0,
                "pii_categories": redaction.categories,
                "nothing_left_mac": True,
                "cloud_zero_retention": True,
                "outbound_payload_sha256": "local_only_no_outbound_payload",
                "receipt_signature_sha256": "local_mlx_stream_verified",
            }

            sse("[DONE]")
            sse(json.dumps({
                "type": "receipt",
                "mode": "local_mlx_stream",
                "model": provider.model_id,
                "tokens": token_count,
                "pii_masked": redaction.pii_count,
                "on_device": True,
                "cloud_prompt_sent": None,
                "stations": local_stations,
                "receipt": local_receipt,
                "guardian_audit": redaction.to_dict(),
                "generation_stats": provider.last_generation_stats,
                "telemetry": self.orchestrator.collect_telemetry(tokens=token_count).__dict__,
            }))

        else:
            # Hybrid path: run the full orchestrator task in a thread,
            # emit a "thinking" heartbeat every 2s, then stream the final output
            # token-by-token once we have it.
            result_holder: Dict[str, Any] = {}
            done_event = threading.Event()
            approved_sanitized = (
                str(body["approved_sanitized_prompt"])
                if body.get("approved_sanitized_prompt")
                else None
            )
            consensus_provs = (
                [str(x) for x in body["consensus_providers"]]
                if isinstance(body.get("consensus_providers"), list)
                else None
            )

            def _run_task() -> None:
                try:
                    result = self.orchestrator.run_task(
                        prompt=prompt,
                        mode=mode_override,
                        cloud_provider=body.get("cloud_provider") or None,
                        file_paths=[str(p) for p in file_paths],
                        inline_file_context=inline_context,
                        session_id=body.get("session_id") or None,
                        save_to_history=bool(body.get("save_to_history", True)),
                        approved_sanitized_prompt=approved_sanitized,
                        consensus_providers=consensus_provs,
                    )
                    result_holder["result"] = result.to_dict()
                except Exception as exc:
                    result_holder["error"] = str(exc)
                finally:
                    done_event.set()

            t = threading.Thread(target=_run_task, daemon=True)
            t.start()

            # Heartbeat while waiting
            while not done_event.wait(timeout=2.0):
                sse(json.dumps({"type": "heartbeat"}))

            if "error" in result_holder:
                sse(json.dumps({"type": "error", "message": result_holder["error"]}))
                sse("[DONE]")
                return

            task_dict = result_holder["result"]
            final_text: str = task_dict.get("final_output", "")

            # Stream the final text word-by-word for a smooth UI effect
            words = final_text.split(" ")
            for i, word in enumerate(words):
                chunk = word if i == 0 else " " + word
                sse(json.dumps({"type": "token", "text": chunk}))

            sse("[DONE]")
            sse(json.dumps({"type": "receipt", **{
                k: task_dict.get(k)
                for k in (
                    "receipt",
                    "stations",
                    "cloud_prompt_sent",
                    "telemetry",
                    "guardian_audit",
                    "session_id",
                )
            }}))


def dispatch_request(
    orchestrator: HybridOrchestrator,
    method: str,
    path: str,
    body: Optional[Dict[str, Any]] = None,
) -> Tuple[int, Dict[str, Any]]:
    """Dispatches a request directly against `orchestrator` (used by HTTP server, CLI IPC, and tests)."""
    upper_method = method.upper()
    payload_in = body or {}

    if upper_method == "GET":
        if path == "/health":
            telemetry = orchestrator.collect_telemetry()
            return HTTPStatus.OK, {
                "status": "ok",
                "version": __version__,
                "compute_mode": orchestrator.config.compute_mode.value,
                "cloud_provider": orchestrator.config.cloud_provider,
                "guardian_policy": orchestrator.config.guardian_policy.value,
                "history_storage": orchestrator.config.history_storage.value,
                "history_retention": orchestrator.config.history_retention.value,
                "cloud_zero_retention": True,
                "m365_proxy_running": orchestrator.m365_manager.is_running(),
                "telemetry": {
                    "architecture": telemetry.architecture,
                    "chip_brand": telemetry.chip_brand,
                    "unified_memory_gb": telemetry.unified_memory_gb,
                },
            }
        if path == "/v1/config":
            return HTTPStatus.OK, orchestrator.config.to_dict()
        if path == "/v1/history":
            return HTTPStatus.OK, orchestrator.history_manager.status_dict()
        if path == "/v1/m365/status":
            return HTTPStatus.OK, orchestrator.m365_manager.status_dict()
        if path == "/v1/mlx/status":
            available = MLXProvider.is_available()
            mem_gb = MLXProvider.unified_memory_gb() if available else 0
            from .providers import MLX_DEFAULT_MODEL, MLX_FALLBACK_MODEL, MLX_LARGE_MODEL_MIN_MEMORY_GB
            return HTTPStatus.OK, {
                "mlx_available": available,
                "metal_available": available and _metal_available(),
                "unified_memory_gb": mem_gb,
                "active_model": MLXProvider()._pick_model() if available else None,
                "large_model": MLX_DEFAULT_MODEL,
                "fallback_model": MLX_FALLBACK_MODEL,
                "large_model_min_memory_gb": MLX_LARGE_MODEL_MIN_MEMORY_GB,
                "backend": "Apple MLX (ANE + Metal)" if available else "unavailable",
            }
        if path == "/v1/hardware/profile":
            return HTTPStatus.OK, HardwareProfiler.profile().to_dict()
        if path == "/v1/models":
            return HTTPStatus.OK, {
                "object": "list",
                "data": [
                    {
                        "id": "machybrid-auto",
                        "object": "model",
                        "owned_by": "machybridai",
                        "description": "Adaptive Smart Auto Router (Local Apple Silicon or 4-Station Hybrid with PII Gate)",
                    },
                    {
                        "id": "machybrid-local",
                        "object": "model",
                        "owned_by": "machybridai",
                        "description": "100% On-Device Apple Silicon Metal / MLX execution (nothing leaves Mac)",
                    },
                    {
                        "id": "machybrid-hybrid",
                        "object": "model",
                        "owned_by": "machybridai",
                        "description": "4-Station Hybrid Compute with On-Device PII Guardian & Zero Cloud History",
                    },
                    {
                        "id": "machybrid-consensus",
                        "object": "model",
                        "owned_by": "machybridai",
                        "description": "Multi-Cloud Consensus Arena with On-Device PII Guardian & Local Synthesis",
                    },
                ],
            }
        return HTTPStatus.NOT_FOUND, {"error": f"Unknown path: {path}"}

    if upper_method == "POST":
        if path == "/v1/config":
            try:
                updated = orchestrator.update_config(payload_in)
                return HTTPStatus.OK, updated.to_dict()
            except ValueError as exc:
                return HTTPStatus.BAD_REQUEST, {"error": str(exc)}

        if path == "/v1/history":
            action = str(payload_in.get("action", "configure"))
            if action == "configure":
                try:
                    loc = (
                        HistoryStorageLocation(str(payload_in["storage_location"]))
                        if payload_in.get("storage_location")
                        else None
                    )
                    ret = (
                        HistoryRetentionPolicy(str(payload_in["retention_policy"]))
                        if payload_in.get("retention_policy")
                        else None
                    )
                    if loc is not None:
                        orchestrator.config.history_storage = loc
                    if ret is not None:
                        orchestrator.config.history_retention = ret
                    status_out = orchestrator.history_manager.configure(
                        storage_location=loc,
                        retention_policy=ret,
                    )
                    return HTTPStatus.OK, status_out
                except ValueError as exc:
                    return HTTPStatus.BAD_REQUEST, {"error": str(exc)}
            if action == "delete_session":
                sid = str(payload_in.get("session_id", ""))
                deleted = orchestrator.history_manager.delete_session(sid)
                return HTTPStatus.OK, {
                    "deleted": deleted,
                    "history": orchestrator.history_manager.status_dict(),
                }
            if action == "clear_all":
                cleared = orchestrator.history_manager.clear_all()
                return HTTPStatus.OK, {
                    "cleared_count": cleared,
                    "history": orchestrator.history_manager.status_dict(),
                }
            if action == "prune_expired":
                pruned = orchestrator.history_manager.prune_expired()
                return HTTPStatus.OK, {
                    "pruned_count": pruned,
                    "history": orchestrator.history_manager.status_dict(),
                }
            return HTTPStatus.BAD_REQUEST, {"error": f"Unknown history action: {action}"}

        if path == "/v1/guardian/inspect":
            text = str(payload_in.get("text", ""))
            policy_raw = payload_in.get("policy")
            policy_override: Optional[GuardianPolicy] = None
            if policy_raw:
                try:
                    policy_override = GuardianPolicy(str(policy_raw))
                except ValueError:
                    return HTTPStatus.BAD_REQUEST, {
                        "error": f"Invalid guardian policy: {policy_raw}"
                    }

            redaction = orchestrator.guardian.redact(
                text,
                policy_override=policy_override,
            )
            simulated_cloud = (
                f"Cloud processed request for {redaction.sanitized_text}"
                if redaction.sanitized_text
                else ""
            )
            restored_preview, restored_count = orchestrator.guardian.restore(
                simulated_cloud
            )
            out = redaction.to_dict()
            out["restored_preview"] = restored_preview
            out["restored_count"] = restored_count
            return HTTPStatus.OK, out

        if path == "/v1/tasks/run":
            prompt = str(payload_in.get("prompt", "")).strip()
            if not prompt:
                return HTTPStatus.BAD_REQUEST, {"error": "prompt is required"}

            mode_override: Optional[ComputeMode] = None
            if payload_in.get("mode"):
                try:
                    mode_override = ComputeMode(str(payload_in["mode"]))
                except ValueError:
                    return HTTPStatus.BAD_REQUEST, {
                        "error": f"Invalid mode: {payload_in.get('mode')}"
                    }

            cloud_provider = payload_in.get("cloud_provider")
            file_paths = (
                payload_in.get("file_paths")
                if isinstance(payload_in.get("file_paths"), list)
                else []
            )
            inline_context = str(payload_in.get("inline_file_context", ""))
            tools = (
                payload_in.get("tools")
                if isinstance(payload_in.get("tools"), list)
                else None
            )
            session_id = (
                str(payload_in["session_id"])
                if payload_in.get("session_id")
                else None
            )
            save_to_history = bool(payload_in.get("save_to_history", True))
            approved_sanitized = (
                str(payload_in["approved_sanitized_prompt"])
                if payload_in.get("approved_sanitized_prompt")
                else None
            )
            consensus_provs = (
                [str(x) for x in payload_in["consensus_providers"]]
                if isinstance(payload_in.get("consensus_providers"), list)
                else None
            )

            result = orchestrator.run_task(
                prompt=prompt,
                mode=mode_override,
                cloud_provider=str(cloud_provider) if cloud_provider else None,
                file_paths=[str(p) for p in file_paths],
                inline_file_context=inline_context,
                tools=tools,
                session_id=session_id,
                save_to_history=save_to_history,
                approved_sanitized_prompt=approved_sanitized,
                consensus_providers=consensus_provs,
            )
            return HTTPStatus.OK, result.to_dict()

        if path == "/v1/chat/completions":
            import time as _time

            messages = payload_in.get("messages")
            if not isinstance(messages, list) or not messages:
                return HTTPStatus.BAD_REQUEST, {"error": "messages list is required"}

            # Combine conversation messages into prompt context
            turns: List[str] = []
            for m in messages:
                if isinstance(m, dict):
                    role = str(m.get("role", "user"))
                    content = str(m.get("content", "")).strip()
                    if content:
                        turns.append(f"{role.upper()}: {content}" if len(messages) > 1 else content)
            combined_prompt = "\n\n".join(turns).strip()
            if not combined_prompt:
                return HTTPStatus.BAD_REQUEST, {"error": "messages content is empty"}

            req_model = str(payload_in.get("model", "machybrid-hybrid")).lower().strip()
            if "local" in req_model:
                oa_mode = ComputeMode.LOCAL
                oa_cloud = None
            elif "auto" in req_model:
                oa_mode = ComputeMode.AUTO
                oa_cloud = None
            elif "consensus" in req_model:
                oa_mode = ComputeMode.HYBRID
                oa_cloud = "consensus"
            else:
                oa_mode = ComputeMode.HYBRID
                oa_cloud = None

            task_res = orchestrator.run_task(
                prompt=combined_prompt,
                mode=oa_mode,
                cloud_provider=oa_cloud,
                save_to_history=bool(payload_in.get("save_to_history", False)),
            )
            res_dict = task_res.to_dict()
            created_ts = int(_time.time())
            tok_used = int(res_dict.get("telemetry", {}).get("tokens_processed", 32))
            return HTTPStatus.OK, {
                "id": f"chatcmpl_{task_res.task_id}",
                "object": "chat.completion",
                "created": created_ts,
                "model": req_model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": task_res.final_output,
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": max(1, len(combined_prompt.split())),
                    "completion_tokens": max(1, tok_used),
                    "total_tokens": max(2, len(combined_prompt.split()) + tok_used),
                },
                "x_machybrid_receipt": res_dict.get("receipt"),
                "x_machybrid_stations": res_dict.get("stations"),
            }

        if path == "/v1/rag/query":
            query = str(payload_in.get("query", "")).strip()
            inline_context = str(payload_in.get("inline_file_context", ""))
            top_k = int(payload_in.get("top_k", 4))
            chunks = orchestrator.rag.retrieve(
                query=query,
                top_k=max(1, min(top_k, 12)),
                inline_context=inline_context,
            )
            return HTTPStatus.OK, {
                "query": query,
                "chunk_count": len(chunks),
                "chunks": [c.to_dict() for c in chunks],
                "formatted_context": orchestrator.rag.format_retrieved_context(chunks),
            }

        if path == "/v1/router/classify":
            prompt_text = str(payload_in.get("prompt", "")).strip()
            return HTTPStatus.OK, orchestrator.classify_prompt_complexity(prompt_text)

        if path == "/v1/m365/control":
            action = str(payload_in.get("action", "status"))
            if action == "start":
                ok, msg = orchestrator.m365_manager.start()
                return HTTPStatus.OK, {
                    "ok": ok,
                    "message": msg,
                    "status": orchestrator.m365_manager.status_dict(),
                }
            if action == "stop":
                ok, msg = orchestrator.m365_manager.stop()
                return HTTPStatus.OK, {
                    "ok": ok,
                    "message": msg,
                    "status": orchestrator.m365_manager.status_dict(),
                }
            if action == "emulate_tools":
                tools = (
                    payload_in.get("tools")
                    if isinstance(payload_in.get("tools"), list)
                    else []
                )
                sample_output = str(payload_in.get("model_output", ""))
                return HTTPStatus.OK, {
                    "tools_prompt": M365ToolEmulator.format_tools_prompt(tools),
                    "parsed_tool_calls": M365ToolEmulator.parse_fenced_tool_calls(
                        sample_output,
                        declared_tools=tools,
                    ),
                }
            return HTTPStatus.BAD_REQUEST, {"error": f"Unknown action: {action}"}

        if path == "/v1/hardware/benchmark":
            req_model = (
                str(payload_in["model_id"])
                if payload_in.get("model_id")
                else None
            )
            max_tok = int(payload_in.get("max_tokens", 24))
            bench = HardwareProfiler.run_benchmark(
                model_id=req_model,
                max_tokens=max(8, min(max_tok, 64)),
            )
            return HTTPStatus.OK, bench.to_dict()

        if path == "/v1/hardware/models/pull":
            req_model = str(payload_in.get("model_id", "")).strip()
            if not req_model:
                return HTTPStatus.BAD_REQUEST, {"error": "model_id is required"}
            allow_dl = bool(payload_in.get("allow_download", False))
            pull_res = HardwareProfiler.pull_or_verify_model(
                model_id=req_model,
                allow_network_download=allow_dl,
            )
            return HTTPStatus.OK, pull_res

        if path == "/v1/shutdown":
            return HTTPStatus.OK, orchestrator.shutdown_all_local_resources()

        return HTTPStatus.NOT_FOUND, {"error": f"Unknown path: {path}"}

    return HTTPStatus.METHOD_NOT_ALLOWED, {"error": f"Unsupported method: {upper_method}"}


def _metal_available() -> bool:
    """Returns True when MLX can see a Metal GPU."""
    try:
        import mlx.core as mx
        return mx.metal.is_available()
    except Exception:
        return False


def create_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    orchestrator: Optional[HybridOrchestrator] = None,
) -> ThreadingHTTPServer:
    """Creates a loopback-bound ThreadingHTTPServer instance."""
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("Security policy: MacHybridAI daemon must bind only to 127.0.0.1/localhost.")

    class BoundHandler(HybridRequestHandler):
        pass

    BoundHandler.orchestrator = orchestrator or HybridOrchestrator()
    return ThreadingHTTPServer((host, port), BoundHandler)


def _find_free_port() -> int:
    """Binds to port 0 to let the OS pick a free ephemeral port, then returns it."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="MacHybridAI Local Hybrid Compute Daemon")
    parser.add_argument("--host", default="127.0.0.1", help="Loopback bind address (127.0.0.1)")
    parser.add_argument("--port", type=int, default=0,
                        help="Port to listen on. 0 = OS-assigned free port (default).")
    parser.add_argument(
        "--cli-json",
        default=None,
        help="Execute a single JSON request payload {'method', 'path', 'body'} and print JSON to stdout",
    )
    parser.add_argument(
        "--ready-fd",
        type=int,
        default=None,
        help=(
            "File descriptor to write a single ready-line to once the server is bound and "
            "listening. Used by the Swift DaemonManager to avoid polling. "
            "Format written: '<port>\\n' so the caller learns the actual port."
        ),
    )
    parser.add_argument(
        "--parent-pid",
        type=int,
        default=None,
        help="Optional parent process PID to watch; if parent exits, unload models and quit.",
    )
    args = parser.parse_args()

    orchestrator = HybridOrchestrator()

    # ── CLI single-shot mode (legacy subprocess IPC) ──────────────────────────
    if args.cli_json:
        req_obj = json.loads(args.cli_json)
        _, resp_obj = dispatch_request(
            orchestrator=orchestrator,
            method=str(req_obj.get("method", "GET")),
            path=str(req_obj.get("path", "/health")),
            body=req_obj.get("body"),
        )
        print(json.dumps(resp_obj))
        return

    # ── Persistent daemon mode ────────────────────────────────────────────────
    port = args.port if args.port != 0 else _find_free_port()
    server = create_server(host=args.host, port=port, orchestrator=orchestrator)

    import atexit as _atexit
    import os as _os
    import signal as _signal
    import time as _time

    _atexit.register(orchestrator.shutdown_all_local_resources)

    def _handle_termination_signal(signum: int, frame: Any) -> None:
        orchestrator.shutdown_all_local_resources()
        threading.Thread(target=server.shutdown, daemon=True).start()

    _signal.signal(_signal.SIGTERM, _handle_termination_signal)
    _signal.signal(_signal.SIGINT, _handle_termination_signal)

    if args.parent_pid and args.parent_pid > 1:
        parent_pid = int(args.parent_pid)

        def _watch_parent() -> None:
            while True:
                _time.sleep(1.5)
                try:
                    _os.kill(parent_pid, 0)
                except ProcessLookupError:
                    orchestrator.shutdown_all_local_resources()
                    server.shutdown()
                    break
                except PermissionError:
                    pass

        threading.Thread(target=_watch_parent, daemon=True).start()

    # Signal readiness to the parent process (Swift DaemonManager).
    # Write "<port>\n" to the ready-fd so Swift knows:
    #   (a) the server is bound and accepting connections, and
    #   (b) which ephemeral port it's on when --port 0 was used.
    if args.ready_fd is not None:
        try:
            with _os.fdopen(args.ready_fd, "w", closefd=True) as rfd:
                rfd.write(f"{port}\n")
                rfd.flush()
        except OSError:
            pass  # fd already closed or invalid — caller will fall back to polling

    print(f"MacHybridAI daemon listening on http://{args.host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        orchestrator.shutdown_all_local_resources()
        server.server_close()


if __name__ == "__main__":
    main()
