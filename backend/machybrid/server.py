"""Local Loopback HTTP Daemon for MacHybridAI (`127.0.0.1:8765`).

Binds strictly to localhost so no external network host can invoke the hybrid engine.
Provides JSON endpoints for the native macOS SwiftUI app and CLI:
- `GET /health`
- `GET /v1/config` & `POST /v1/config`
- `POST /v1/guardian/inspect`
- `POST /v1/tasks/run`
- `GET /v1/m365/status` & `POST /v1/m365/control`
"""

from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional, Tuple

from . import __version__
from .guardian import GuardianPolicy
from .m365_proxy import M365ToolEmulator
from .orchestrator import ComputeMode, HybridOrchestrator

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
        body = self._read_json_body()
        if body is None:
            return
        status, payload = dispatch_request(self.orchestrator, "POST", self.path, body)
        self._send_json(status, payload)


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
                "m365_proxy_running": orchestrator.m365_manager.is_running(),
                "telemetry": {
                    "architecture": telemetry.architecture,
                    "chip_brand": telemetry.chip_brand,
                    "unified_memory_gb": telemetry.unified_memory_gb,
                },
            }
        if path == "/v1/config":
            return HTTPStatus.OK, orchestrator.config.to_dict()
        if path == "/v1/m365/status":
            return HTTPStatus.OK, orchestrator.m365_manager.status_dict()
        return HTTPStatus.NOT_FOUND, {"error": f"Unknown path: {path}"}

    if upper_method == "POST":
        if path == "/v1/config":
            try:
                updated = orchestrator.update_config(payload_in)
                return HTTPStatus.OK, updated.to_dict()
            except ValueError as exc:
                return HTTPStatus.BAD_REQUEST, {"error": str(exc)}

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

            result = orchestrator.run_task(
                prompt=prompt,
                mode=mode_override,
                cloud_provider=str(cloud_provider) if cloud_provider else None,
                file_paths=[str(p) for p in file_paths],
                inline_file_context=inline_context,
                tools=tools,
            )
            return HTTPStatus.OK, result.to_dict()

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

        return HTTPStatus.NOT_FOUND, {"error": f"Unknown path: {path}"}

    return HTTPStatus.METHOD_NOT_ALLOWED, {"error": f"Unsupported method: {upper_method}"}


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


def main() -> None:
    parser = argparse.ArgumentParser(description="MacHybridAI Local Hybrid Compute Daemon")
    parser.add_argument("--host", default="127.0.0.1", help="Loopback bind address (127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Port number (default: 8765)")
    parser.add_argument(
        "--cli-json",
        default=None,
        help="Execute a single JSON request payload {'method', 'path', 'body'} and print JSON to stdout",
    )
    args = parser.parse_args()

    orchestrator = HybridOrchestrator()
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

    server = create_server(host=args.host, port=args.port, orchestrator=orchestrator)
    print(f"MacHybridAI daemon listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
