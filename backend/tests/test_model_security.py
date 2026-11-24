"""Unit tests for Model Supply-Chain Security, SHA-256 Lockfile, Apple Foundation Models, and HF Bypass."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

from machybrid.cli import main
from machybrid.model_security import (
    HUGGINGFACE_OVERRIDE_WARNING,
    ModelSecuritySettings,
    ModelTrustPolicy,
    audit_model_directory,
    pin_model_to_lockfile,
    sanitize_local_model_dir,
)
from machybrid.orchestrator import HybridOrchestrator
from machybrid.profiler import SAFE_DOWNLOAD_ALLOW_PATTERNS, HardwareProfiler
from machybrid.providers import AppleFoundationModelsProvider, MLXProvider
from machybrid.server import dispatch_request


def _make_clean_model_dir(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "config.json").write_text(json.dumps({"model_type": "gemma3"}), encoding="utf-8")
    (root / "tokenizer_config.json").write_text(
        json.dumps({"chat_template": "{% for m in messages %}{{ m.content }}{% endfor %}"}),
        encoding="utf-8",
    )
    (root / "model.safetensors").write_bytes(b"SAFETENSORS_HEADER_BYTES_DEMO_1234567890")
    return root


class TestModelSupplyChainSecurity(unittest.TestCase):
    def test_strict_default_blocks_community_hf_but_allows_first_party_local_and_apple_signed(self) -> None:
        strict = ModelSecuritySettings(allow_unverified_huggingface=False)
        self.assertEqual(strict.policy, ModelTrustPolicy.STRICT_VERIFIED)

        # 1. Apple-signed OS Foundation Model always allowed
        res_apple = audit_model_directory("apple-foundation-model", settings=strict)
        self.assertTrue(res_apple.allowed)
        self.assertEqual(res_apple.publisher_trust, "apple_signed")

        with tempfile.TemporaryDirectory() as tmp:
            clean_dir = _make_clean_model_dir(Path(tmp) / "model")

            # 2. First-party trusted publisher allowed
            res_fp = audit_model_directory("google/gemma-3-4b-it", model_dir=clean_dir, settings=strict)
            self.assertTrue(res_fp.allowed)
            self.assertEqual(res_fp.publisher_trust, "first_party")

            # 3. Explicit verified local directory allowed (zero Hugging Face)
            res_local = audit_model_directory(
                str(clean_dir), model_dir=clean_dir, settings=strict, is_local_dir=True
            )
            self.assertTrue(res_local.allowed)
            self.assertEqual(res_local.publisher_trust, "local_verified_dir")

            # 4. Community Hugging Face org BLOCKED under strict default
            res_comm = audit_model_directory(
                "mlx-community/gemma-3-4b-it-4bit", model_dir=clean_dir, settings=strict
            )
            self.assertFalse(res_comm.allowed)
            self.assertEqual(res_comm.publisher_trust, "community_unverified")
            self.assertTrue(any("Blocked unverified Hugging Face" in e for e in res_comm.errors))

    def test_explicit_huggingface_override_allows_community_with_warning_but_still_blocks_malicious_files(self) -> None:
        override = ModelSecuritySettings(
            allow_unverified_huggingface=True,
            huggingface_override_acknowledged=True,
        )
        self.assertEqual(override.policy, ModelTrustPolicy.HUGGINGFACE_OVERRIDE)

        with tempfile.TemporaryDirectory() as tmp:
            clean_dir = _make_clean_model_dir(Path(tmp) / "clean")
            res_ok = audit_model_directory(
                "mlx-community/gemma-3-4b-it-4bit", model_dir=clean_dir, settings=override
            )
            self.assertTrue(res_ok.allowed)
            self.assertTrue(res_ok.override_used)
            self.assertIn(HUGGINGFACE_OVERRIDE_WARNING, res_ok.warnings)

            # Even with override ON, pickle/Python/executable files are HARD BLOCKED!
            evil_dir = _make_clean_model_dir(Path(tmp) / "evil_py")
            (evil_dir / "modeling_custom.py").write_text("import os\n", encoding="utf-8")
            res_py = audit_model_directory(
                "mlx-community/gemma-3-4b-it-4bit", model_dir=evil_dir, settings=override
            )
            self.assertFalse(res_py.allowed)
            self.assertTrue(any("pickle/executable" in e for e in res_py.errors))

            # Even with override ON, Jinja2 SSTI in chat_template is HARD BLOCKED!
            ssti_dir = _make_clean_model_dir(Path(tmp) / "evil_ssti")
            (ssti_dir / "tokenizer_config.json").write_text(
                json.dumps({"chat_template": "{{ ''.__class__.__mro__[1].__subclasses__() }}"}),
                encoding="utf-8",
            )
            res_ssti = audit_model_directory(
                "mlx-community/gemma-3-4b-it-4bit", model_dir=ssti_dir, settings=override
            )
            self.assertFalse(res_ssti.allowed)
            self.assertTrue(any("suspicious pattern" in e for e in res_ssti.errors))

            # Even with override ON, auto_map in config.json is HARD BLOCKED!
            automap_dir = _make_clean_model_dir(Path(tmp) / "evil_automap")
            (automap_dir / "config.json").write_text(
                json.dumps({"model_type": "custom", "auto_map": {"AutoModel": "evil.Model"}}),
                encoding="utf-8",
            )
            res_am = audit_model_directory(
                "mlx-community/gemma-3-4b-it-4bit", model_dir=automap_dir, settings=override
            )
            self.assertFalse(res_am.allowed)
            self.assertTrue(any("auto_map" in e for e in res_am.errors))

    def test_sha256_lockfile_pinning_allows_verified_and_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model_dir = _make_clean_model_dir(root / "pinned_model")
            lockfile = root / "models.lock.json"

            entry = pin_model_to_lockfile(
                model_id="mlx-community/gemma-3-4b-it-4bit",
                model_dir=model_dir,
                lockfile_path=lockfile,
            )
            self.assertEqual(len(entry["manifest_sha256"]), 64)

            strict_with_lock = ModelSecuritySettings(
                allow_unverified_huggingface=False,
                lockfile_path=str(lockfile),
            )
            # Pinned model passes even under strict protection because SHA-256 matches
            res_valid = audit_model_directory(
                "mlx-community/gemma-3-4b-it-4bit",
                model_dir=model_dir,
                settings=strict_with_lock,
            )
            self.assertTrue(res_valid.allowed)
            self.assertTrue(res_valid.locked_sha256_verified)

            # Tamper 1 byte of the safetensors file -> MUST FAIL CLOSED!
            (model_dir / "model.safetensors").write_bytes(b"TAMPERED_WEIGHTS_BYTES_9999")
            res_tampered = audit_model_directory(
                "mlx-community/gemma-3-4b-it-4bit",
                model_dir=model_dir,
                settings=strict_with_lock,
            )
            self.assertFalse(res_tampered.allowed)
            self.assertFalse(res_tampered.locked_sha256_verified)
            self.assertTrue(any("SHA-256 lockfile mismatch" in e for e in res_tampered.errors))

    def test_mlx_load_locks_trust_remote_code_false_and_apple_fm_provider_works(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local_dir = _make_clean_model_dir(Path(tmp) / "verified_local")
            fake_mlx_core = MagicMock()
            fake_mlx_core.device_info.return_value = {"max_recommended_working_set_size": 0}
            fake_mlx_lm = MagicMock()
            fake_mlx_lm.load.return_value = (object(), object())

            MLXProvider._model_cache.clear()
            with patch(
                "machybrid.providers.HardwareProfiler.get_mlx_modules",
                return_value=(fake_mlx_core, fake_mlx_lm, ""),
            ):
                prov = MLXProvider(
                    security_settings=ModelSecuritySettings(allow_unverified_huggingface=False),
                    local_model_dir=str(local_dir),
                )
                prov._load_model()
            MLXProvider._model_cache.clear()

            fake_mlx_lm.load.assert_called_once()
            _, kwargs = fake_mlx_lm.load.call_args
            self.assertEqual(kwargs.get("tokenizer_config"), {"trust_remote_code": False})

        # AppleFoundationModelsProvider uses compiled Swift binary when available
        fake_check = MagicMock(
            returncode=0,
            stdout=json.dumps({"available": True, "reason": "Apple-signed SystemLanguageModel ready."}),
            stderr="",
        )
        fake_gen = MagicMock(
            returncode=0,
            stdout=json.dumps(
                {
                    "ok": True,
                    "output_text": "Apple-signed on-device answer.",
                    "model_name": "Apple On-Device Foundation Model (Apple-Signed)",
                    "signer": "Apple Inc.",
                }
            ),
            stderr="",
        )
        AppleFoundationModelsProvider._availability_cache = None
        with patch.object(AppleFoundationModelsProvider, "_find_swift_binary", return_value="/usr/local/bin/MacHybridAI"):
            with patch("machybrid.providers.subprocess.run", side_effect=[fake_check, fake_gen]):
                avail, reason = AppleFoundationModelsProvider.check_availability(force_refresh=True)
                self.assertTrue(avail)
                self.assertIn("Apple-signed", reason)
                resp = AppleFoundationModelsProvider().generate("Hello")
                self.assertEqual(resp.output_text, "Apple-signed on-device answer.")
                self.assertTrue(resp.metadata.get("apple_signed"))
                self.assertFalse(resp.metadata.get("huggingface_used"))
        AppleFoundationModelsProvider._availability_cache = None

    def test_cli_security_subcommand_and_server_endpoint(self) -> None:
        # 1. `machybrid security allow-hf --json` WITHOUT --confirm-warning must refuse!
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["--json", "security", "allow-hf"])
        self.assertEqual(rc, 1)
        data = json.loads(buf.getvalue())
        self.assertFalse(data["enabled"])

        # 2. `machybrid security status --json`
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["--json", "security", "status"])
        self.assertEqual(rc, 0)
        sec_status = json.loads(buf.getvalue())
        self.assertIn("security", sec_status)
        self.assertTrue(sec_status["security"]["trust_remote_code_forced_false"])

        # 3. `GET /v1/security/models` on loopback server
        orch = HybridOrchestrator()
        code, body = dispatch_request(orch, "GET", "/v1/security/models")
        self.assertEqual(int(code), 200)
        self.assertIn("security", body)
        self.assertIn("apple_foundation_models", body)

        # 4. CLI auto-defaults local_backend to `apple_fm` when Apple Foundation Models are available
        with patch.object(
            AppleFoundationModelsProvider,
            "check_availability",
            return_value=(True, "Apple-signed SystemLanguageModel is available on this Mac."),
        ):
            buf_auto = io.StringIO()
            with redirect_stdout(buf_auto):
                rc = main(["--json", "security", "status"])
            self.assertEqual(rc, 0)
            auto_data = json.loads(buf_auto.getvalue())
            self.assertEqual(auto_data["local_backend"], "apple_fm")

            # Explicit --local-backend mlx still overrides auto-default
            buf_mlx = io.StringIO()
            with redirect_stdout(buf_mlx):
                rc = main(["--local-backend", "mlx", "--json", "security", "status"])
            self.assertEqual(rc, 0)
            mlx_data = json.loads(buf_mlx.getvalue())
            self.assertEqual(mlx_data["local_backend"], "mlx")

    def test_safe_downloader_usability_scan_and_local_models_folder(self) -> None:
        # 1. SAFE_DOWNLOAD_ALLOW_PATTERNS must never include executable/pickle extensions
        for pat in SAFE_DOWNLOAD_ALLOW_PATTERNS:
            self.assertFalse(pat.endswith((".py", ".pkl", ".bin", ".pt", ".so", ".dylib")))

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hf_dir = root / "hf_hub"
            local_models = root / "Models"
            lockfile = root / "models.lock.json"

            # Create a verified local folder in ~/Models
            local_gemma = _make_clean_model_dir(local_models / "gemma-3-4b-mlx-4bit")

            # Create a cached community MLX model in hf_hub
            snap_dir = _make_clean_model_dir(
                hf_dir / "models--mlx-community--gemma-3-4b-it-4bit" / "snapshots" / ("a" * 40)
            )
            self.assertTrue(snap_dir.is_dir())

            strict = ModelSecuritySettings(allow_unverified_huggingface=False, lockfile_path=str(lockfile))
            HardwareProfiler._hf_inspect_cache.clear()
            scanned = HardwareProfiler.scan_cached_models(
                hf_hub_dir=hf_dir,
                local_models_dir=local_models,
                security_settings=strict,
            )

            # Local ~/Models folder is immediately USABLE
            local_entry = next(m for m in scanned if m.backend == "mlx_local_dir")
            self.assertEqual(Path(local_entry.local_path).resolve(), local_gemma.resolve())
            self.assertTrue(local_entry.is_usable)
            self.assertEqual(local_entry.publisher_trust, "local_verified_dir")

            # Unpinned community HF cache model is downloaded (is_complete=True) but NOT yet usable under strict policy
            comm_entry = next(m for m in scanned if m.model_id == "mlx-community/gemma-3-4b-it-4bit")
            self.assertTrue(comm_entry.is_complete)
            self.assertFalse(comm_entry.is_usable)
            self.assertFalse(comm_entry.is_pinned)

            # Running audited verify + auto_pin pins its SHA-256 -> becomes USABLE under strict policy!
            pin_res = HardwareProfiler.pull_or_verify_model(
                model_id="mlx-community/gemma-3-4b-it-4bit",
                hf_hub_dir=hf_dir,
                allow_network_download=False,
                security_settings=strict,
                auto_pin=True,
            )
            self.assertTrue(pin_res["ok"])
            self.assertEqual(pin_res["status"], "ready_pinned")
            self.assertEqual(len(pin_res["pinned_sha256"]), 64)

            scanned_after = HardwareProfiler.scan_cached_models(
                hf_hub_dir=hf_dir,
                local_models_dir=local_models,
                security_settings=strict,
            )
            comm_after = next(m for m in scanned_after if m.model_id == "mlx-community/gemma-3-4b-it-4bit")
            self.assertTrue(comm_after.is_usable)
            self.assertTrue(comm_after.is_pinned)

            # Strict policy blocks unverified community network download when not cached
            blocked_dl = HardwareProfiler.pull_or_verify_model(
                model_id="mlx-community/gemma-3-12b-it-4bit",
                hf_hub_dir=hf_dir,
                allow_network_download=True,
                security_settings=strict,
            )
            self.assertFalse(blocked_dl["ok"])
            self.assertEqual(blocked_dl["status"], "blocked_by_supply_chain_policy")

            # Local self-quantization rejects community repos and accepts first-party only
            bad_conv = HardwareProfiler.convert_first_party_to_local_mlx(
                repo_id="mlx-community/gemma-3-4b-it-4bit",
                models_root=local_models,
                security_settings=strict,
            )
            self.assertFalse(bad_conv["ok"])
            self.assertEqual(bad_conv["status"], "rejected_untrusted_source")

    def test_path_injection_guards_reject_paths_outside_home_and_temp(self) -> None:
        # 1. System directories outside home/temp are strictly rejected
        self.assertIsNone(sanitize_local_model_dir("/etc"))
        self.assertIsNone(sanitize_local_model_dir("/etc/passwd"))
        self.assertIsNone(sanitize_local_model_dir("/usr/bin"))
        self.assertIsNone(sanitize_local_model_dir("/tmp/../../etc/passwd"))

        # 2. HTTP POST /v1/config rejects local_model_dir outside home/temp
        orch = HybridOrchestrator()
        code, body = dispatch_request(orch, "POST", "/v1/config", {"local_model_dir": "/etc"})
        self.assertEqual(int(code), 400)
        self.assertIn("error", body)

        # 3. HTTP POST /v1/config cannot overwrite model_lockfile_path
        orig_lock = orch.config.model_lockfile_path
        code2, body2 = dispatch_request(
            orch,
            "POST",
            "/v1/config",
            {"model_lockfile_path": "/etc/passwd", "huggingface_override_acknowledged": True},
        )
        self.assertEqual(int(code2), 200)
        self.assertEqual(orch.config.model_lockfile_path, orig_lock)
        self.assertTrue(body2["huggingface_override_acknowledged"])

        # 4. Valid temp directory is accepted by sanitize_local_model_dir and POST /v1/config
        with tempfile.TemporaryDirectory() as tmp:
            clean_dir = _make_clean_model_dir(Path(tmp) / "safe_model")
            self.assertIsNotNone(sanitize_local_model_dir(str(clean_dir)))
            code3, body3 = dispatch_request(
                orch, "POST", "/v1/config", {"local_model_dir": str(clean_dir)}
            )
            self.assertEqual(int(code3), 200)
            self.assertEqual(Path(body3["local_model_dir"]).resolve(), clean_dir.resolve())


if __name__ == "__main__":
    unittest.main()
