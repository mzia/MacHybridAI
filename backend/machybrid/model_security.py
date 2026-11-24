"""Model Supply-Chain Security & Verification Policy for MacHybridAI.

Protects local Apple Silicon inference against unverified Hugging Face repositories,
pickle/code-execution artifacts, malicious tokenizer chat templates, and silent weight
tampering:
  1. Defaults to **strict supply-chain protection** (`allow_unverified_huggingface=False`):
     - Prefers Apple-signed on-device Foundation Models (`apple_fm` on macOS 26+) or
       verified air-gapped local directories (`--local-model-dir`) with zero Hugging Face.
     - For MLX repos, only first-party trusted publishers (`apple/`, `google/`, `Qwen/`,
       `meta-llama/`, `mistralai/`, `microsoft/`) pass without explicit bypass.
     - Always enforces `trust_remote_code=False`, rejects `.py`/`.bin`/`.pt`/`.pkl`/`.so`/`.dylib`
       files, inspects `tokenizer_config.json` for `auto_map` & Jinja SSTI patterns, and
       verifies pinned SHA-256 checksums in `models.lock.json` when present.
  2. Supports an **explicit, warning-gated user bypass** (`allow_unverified_huggingface=True`)
     for users who consciously choose to load community Hugging Face conversions (such as
     `mlx-community/*` or `lmstudio-community/*`). Even when bypassed, remote Python code
     and pickle artifacts remain hard-blocked and a clear warning is surfaced.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class ModelTrustPolicy(str, Enum):
    """High-level local model supply-chain trust posture."""

    APPLE_SIGNED_ONLY = "apple_signed_only"
    STRICT_VERIFIED = "strict_verified"
    HUGGINGFACE_OVERRIDE = "huggingface_override"


FIRST_PARTY_MODEL_ORGS = frozenset(
    {
        "apple",
        "google",
        "qwen",
        "meta-llama",
        "mistralai",
        "microsoft",
    }
)

FORBIDDEN_MODEL_EXTENSIONS = frozenset(
    {
        ".py",
        ".pyc",
        ".pyo",
        ".pkl",
        ".pickle",
        ".bin",
        ".pt",
        ".pth",
        ".ckpt",
        ".joblib",
        ".so",
        ".dylib",
        ".sh",
    }
)

_SUSPICIOUS_TEMPLATE_TOKENS = (
    "__class__",
    "__mro__",
    "__subclasses__",
    "__globals__",
    "__builtins__",
    "__import__",
    "os.system",
    "subprocess",
    "eval(",
    "exec(",
)

HUGGINGFACE_OVERRIDE_WARNING = (
    "SECURITY WARNING: Unverified Hugging Face Supply-Chain Override is ENABLED. "
    "Community repositories (such as mlx-community/* or lmstudio-community/*) are NOT "
    "signed by Apple and may be modified by third-party contributors. "
    "Remote Python code (trust_remote_code=False) and pickle/executable files (.py/.bin/.pt/.pkl) "
    "remain blocked. Use `--local-backend apple_fm` (Apple-signed on macOS 26+), "
    "`--local-model-dir <path>`, or `machybrid security revoke-hf` to restore strict protection."
)


def default_security_config_path() -> Path:
    return Path(os.path.expanduser("~/.config/machybrid/security.json"))


def default_lockfile_path() -> Path:
    return Path(os.path.expanduser("~/.config/machybrid/models.lock.json"))


def sanitize_local_model_dir(raw_dir: str) -> Optional[Path]:
    """Validates that a local model directory path resides strictly inside the user's home or temp directory.

    Applies explicit `os.path.normpath` + prefix containment checks to prevent CWE-22 path injection.
    """
    cleaned = (raw_dir or "").strip()
    if not cleaned or "\x00" in cleaned:
        return None
    home_root = os.path.normpath(os.path.realpath(os.path.expanduser("~"))) + os.sep
    tmp_root = os.path.normpath(os.path.realpath(tempfile.gettempdir())) + os.sep
    normalized = os.path.normpath(os.path.realpath(os.path.expanduser(cleaned)))
    if normalized.startswith(home_root):
        return Path(normalized)
    if normalized.startswith(tmp_root):
        return Path(normalized)
    return None


def _sanitize_lockfile_path(lockfile_path: Optional[Path]) -> Path:
    """Resolves and validates a lockfile path within the user's home or temp directory."""
    if lockfile_path is None:
        return default_lockfile_path()
    safe = sanitize_local_model_dir(str(lockfile_path))
    if safe is None:
        return default_lockfile_path()
    return safe


@dataclass
class ModelSecuritySettings:
    """User-controlled local model supply-chain security settings."""

    allow_unverified_huggingface: bool = False
    huggingface_override_acknowledged: bool = False
    apple_signed_only: bool = False
    local_model_dir: str = ""
    lockfile_path: str = ""
    require_lockfile_match: bool = False

    @property
    def policy(self) -> ModelTrustPolicy:
        if self.apple_signed_only and not self.allow_unverified_huggingface:
            return ModelTrustPolicy.APPLE_SIGNED_ONLY
        if self.allow_unverified_huggingface:
            return ModelTrustPolicy.HUGGINGFACE_OVERRIDE
        return ModelTrustPolicy.STRICT_VERIFIED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy": self.policy.value,
            "allow_unverified_huggingface": self.allow_unverified_huggingface,
            "huggingface_override_acknowledged": self.huggingface_override_acknowledged,
            "apple_signed_only": self.apple_signed_only,
            "local_model_dir": self.local_model_dir,
            "lockfile_path": self.lockfile_path or str(default_lockfile_path()),
            "require_lockfile_match": self.require_lockfile_match,
            "first_party_orgs": sorted(FIRST_PARTY_MODEL_ORGS),
            "trust_remote_code_forced_false": True,
            "pickle_and_python_files_blocked": True,
            "warning": HUGGINGFACE_OVERRIDE_WARNING if self.allow_unverified_huggingface else "",
        }

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "ModelSecuritySettings":
        path = config_path or default_security_config_path()
        settings = cls()
        try:
            if path.is_file():
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    settings.allow_unverified_huggingface = bool(
                        raw.get("allow_unverified_huggingface", False)
                    )
                    settings.huggingface_override_acknowledged = bool(
                        raw.get("huggingface_override_acknowledged", False)
                    )
                    settings.apple_signed_only = bool(raw.get("apple_signed_only", False))
                    raw_dir = str(raw.get("local_model_dir", "") or "").strip()
                    safe_dir = sanitize_local_model_dir(raw_dir) if raw_dir else None
                    settings.local_model_dir = str(safe_dir) if safe_dir is not None else ""
                    raw_lock = str(raw.get("lockfile_path", "") or "").strip()
                    safe_lock = sanitize_local_model_dir(raw_lock) if raw_lock else None
                    settings.lockfile_path = str(safe_lock) if safe_lock is not None else ""
                    settings.require_lockfile_match = bool(
                        raw.get("require_lockfile_match", False)
                    )
        except Exception:
            pass

        # Environment override for CI/headless explicit opt-in
        env_override = os.environ.get("MACHYBRID_ALLOW_HF_OVERRIDE", "").strip().lower()
        if env_override in {"1", "true", "yes"}:
            settings.allow_unverified_huggingface = True
            settings.huggingface_override_acknowledged = True
        env_local_dir = os.environ.get("MACHYBRID_LOCAL_MODEL_DIR", "").strip()
        if env_local_dir:
            safe_env_dir = sanitize_local_model_dir(env_local_dir)
            if safe_env_dir is not None:
                settings.local_model_dir = str(safe_env_dir)
        return settings

    def save(self, config_path: Optional[Path] = None) -> Path:
        path = config_path or default_security_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "allow_unverified_huggingface": self.allow_unverified_huggingface,
            "huggingface_override_acknowledged": self.huggingface_override_acknowledged,
            "apple_signed_only": self.apple_signed_only,
            "local_model_dir": self.local_model_dir,
            "lockfile_path": self.lockfile_path,
            "require_lockfile_match": self.require_lockfile_match,
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path


@dataclass
class ModelAuditResult:
    """Result of auditing a local model directory or Hugging Face repo ID before load."""

    allowed: bool
    model_id: str
    publisher_trust: str  # "apple_signed" | "local_verified_dir" | "first_party" | "community_unverified"
    policy_applied: str
    override_used: bool = False
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    locked_sha256_verified: Optional[bool] = None
    files_scanned: int = 0
    resolved_dir: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def classify_model_publisher(model_id: str, is_local_dir: bool = False) -> str:
    """Classifies the supply-chain trust tier of a model identifier."""
    cleaned = (model_id or "").strip()
    if cleaned.lower() in {"apple-foundation-model", "apple_fm", "apple/foundation-model"}:
        return "apple_signed"
    if is_local_dir or cleaned.startswith(("/", "./", "../", "~")):
        return "local_verified_dir"
    if "/" not in cleaned:
        return "community_unverified"
    org = cleaned.split("/", 1)[0].strip().lower()
    if org in FIRST_PARTY_MODEL_ORGS:
        return "first_party"
    return "community_unverified"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def compute_model_directory_digest(model_dir: Path) -> Tuple[str, Dict[str, str]]:
    """Computes a deterministic SHA-256 manifest digest over config, tokenizer, and safetensors files."""
    resolved = sanitize_local_model_dir(str(model_dir))
    if resolved is None:
        raise ValueError("Model directory must reside inside your home or temp directory.")
    file_hashes: Dict[str, str] = {}
    target_names = {"config.json", "tokenizer_config.json", "model.safetensors.index.json"}
    for entry in sorted(resolved.iterdir(), key=lambda p: p.name):
        if not entry.is_file():
            continue
        if entry.name in target_names or entry.suffix.lower() == ".safetensors":
            file_hashes[entry.name] = _sha256_file(entry)

    manifest_hash = hashlib.sha256()
    for fname in sorted(file_hashes.keys()):
        manifest_hash.update(f"{fname}:{file_hashes[fname]}\n".encode("utf-8"))
    return manifest_hash.hexdigest(), file_hashes


def load_model_lockfile(lockfile_path: Optional[Path] = None) -> Dict[str, Any]:
    path = _sanitize_lockfile_path(lockfile_path)
    try:
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                models = data.get("models", data)
                if isinstance(models, dict):
                    return models
    except Exception:
        pass
    return {}


def pin_model_to_lockfile(
    model_id: str,
    model_dir: Path,
    lockfile_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Computes SHA-256 digests for `model_dir` and pins `model_id` in `models.lock.json`."""
    resolved = sanitize_local_model_dir(str(model_dir))
    if resolved is None:
        raise ValueError("Model directory must reside inside your home or temp directory.")
    if not resolved.is_dir():
        raise ValueError(f"Model directory does not exist: {resolved}")

    # Refuse to pin a directory that contains forbidden executable/pickle files
    forbidden = _find_forbidden_files(resolved)
    if forbidden:
        raise ValueError(
            f"Refusing to pin unsafe model directory containing forbidden files: {', '.join(forbidden[:5])}"
        )

    digest, file_hashes = compute_model_directory_digest(resolved)
    commit_sha = resolved.name if len(resolved.name) == 40 and all(c in "0123456789abcdef" for c in resolved.name.lower()) else ""
    entry = {
        "model_id": model_id,
        "publisher_trust": classify_model_publisher(model_id, is_local_dir=(model_id == str(resolved))),
        "commit_sha": commit_sha,
        "manifest_sha256": digest,
        "file_count": len(file_hashes),
        "files": file_hashes,
    }

    path = _sanitize_lockfile_path(lockfile_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: Dict[str, Any] = {}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                existing = loaded.get("models", loaded) if isinstance(loaded.get("models", loaded), dict) else {}
        except Exception:
            existing = {}

    existing[model_id] = entry
    path.write_text(json.dumps({"version": 1, "models": existing}, indent=2) + "\n", encoding="utf-8")
    return entry


def _find_forbidden_files(model_dir: Path) -> List[str]:
    safe_dir = sanitize_local_model_dir(str(model_dir))
    if safe_dir is None:
        return []
    bad: List[str] = []
    for root, _, files in os.walk(safe_dir):
        for fname in sorted(files):
            ext = Path(fname).suffix.lower()
            if ext in FORBIDDEN_MODEL_EXTENSIONS:
                bad.append(os.path.relpath(os.path.join(root, fname), safe_dir))
    return bad


def _audit_tokenizer_config(model_dir: Path) -> List[str]:
    issues: List[str] = []
    safe_dir = sanitize_local_model_dir(str(model_dir))
    if safe_dir is None:
        return issues
    tok_cfg = safe_dir / "tokenizer_config.json"
    if not tok_cfg.is_file():
        return issues
    try:
        raw = json.loads(tok_cfg.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return issues
        if "auto_map" in raw:
            issues.append("tokenizer_config.json declares `auto_map` (remote Python code hook)")
        tmpl = raw.get("chat_template")
        if isinstance(tmpl, str):
            lowered = tmpl.lower()
            for token in _SUSPICIOUS_TEMPLATE_TOKENS:
                if token in lowered:
                    issues.append(
                        f"tokenizer_config.json chat_template contains suspicious pattern `{token}`"
                    )
                    break
    except Exception as exc:
        issues.append(f"tokenizer_config.json is malformed JSON: {exc}")
    return issues


def audit_model_directory(
    model_id: str,
    model_dir: Optional[Path] = None,
    settings: Optional[ModelSecuritySettings] = None,
    is_local_dir: bool = False,
) -> ModelAuditResult:
    """Runs full supply-chain verification on a model ID and (optional) local directory before loading."""
    cfg = settings or ModelSecuritySettings.load()
    trust = classify_model_publisher(model_id, is_local_dir=is_local_dir)
    warnings: List[str] = []
    errors: List[str] = []
    override_used = False
    files_scanned = 0
    resolved_str = ""
    locked_verified: Optional[bool] = None

    # 1. Apple-signed OS Foundation Models always pass with zero Hugging Face involvement
    if trust == "apple_signed":
        return ModelAuditResult(
            allowed=True,
            model_id=model_id,
            publisher_trust="apple_signed",
            policy_applied=cfg.policy.value,
            override_used=False,
            warnings=[],
            errors=[],
            locked_sha256_verified=True,
        )

    # 2. If apple_signed_only is active and user did NOT enable override, block all non-Apple/non-local-dir models
    if cfg.apple_signed_only and not cfg.allow_unverified_huggingface and trust != "local_verified_dir":
        errors.append(
            f"Blocked `{model_id}`: Apple-Signed Only policy is active. "
            "Use `--local-backend apple_fm` (Apple Foundation Models), `--local-model-dir <path>`, "
            "or explicitly enable the warning-gated Hugging Face override."
        )

    # 3. Inspect local directory contents for forbidden pickle/Python files & malicious tokenizer configs
    resolved_path: Optional[Path] = None
    if model_dir is not None:
        candidate = sanitize_local_model_dir(str(model_dir))
        if candidate is None:
            errors.append(
                f"Blocked unsafe model directory outside allowed home/temp roots for `{model_id}`."
            )
        elif candidate.is_dir():
            resolved_path = candidate
            resolved_str = str(candidate)
            for _, _, files in os.walk(candidate):
                files_scanned += len(files)

            forbidden = _find_forbidden_files(candidate)
            if forbidden:
                errors.append(
                    f"Blocked unsafe model files in `{model_id}` "
                    f"(pickle/executable artifacts forbidden): {', '.join(forbidden[:5])}"
                )

            cfg_json = candidate / "config.json"
            if cfg_json.is_file():
                try:
                    c_raw = json.loads(cfg_json.read_text(encoding="utf-8"))
                    if isinstance(c_raw, dict) and "auto_map" in c_raw:
                        errors.append("config.json declares `auto_map` (remote Python code execution hook)")
                except Exception as exc:
                    errors.append(f"config.json is malformed JSON: {exc}")

            errors.extend(_audit_tokenizer_config(candidate))

    # 4. Check lockfile SHA-256 verification (if pinned or required)
    lock_path = _sanitize_lockfile_path(Path(cfg.lockfile_path) if cfg.lockfile_path else None)
    lock_entries = load_model_lockfile(lock_path)
    pinned = lock_entries.get(model_id)
    if pinned and resolved_path is not None:
        expected_digest = str(pinned.get("manifest_sha256", ""))
        expected_commit = str(pinned.get("commit_sha", ""))
        actual_digest, _ = compute_model_directory_digest(resolved_path)
        if expected_digest and actual_digest != expected_digest:
            locked_verified = False
            errors.append(
                f"SHA-256 lockfile mismatch for `{model_id}`! Expected {expected_digest[:16]}..., "
                f"got {actual_digest[:16]}... (possible cache tampering)."
            )
        elif expected_commit and resolved_path.name != expected_commit:
            locked_verified = False
            errors.append(
                f"Commit SHA mismatch for `{model_id}`: expected pinned commit {expected_commit[:12]}, "
                f"found {resolved_path.name[:12]}."
            )
        else:
            locked_verified = True
    elif cfg.require_lockfile_match and trust != "local_verified_dir":
        locked_verified = False
        errors.append(
            f"Blocked `{model_id}`: `require_lockfile_match` is enabled and this model is not pinned in {lock_path}."
        )

    # 5. Publisher trust policy enforcement (blocks unverified Hugging Face orgs unless override enabled)
    if trust == "community_unverified":
        if locked_verified is True:
            warnings.append(
                f"Community model `{model_id}` allowed because its SHA-256 digest matches your local lockfile."
            )
        elif cfg.allow_unverified_huggingface:
            override_used = True
            warnings.append(HUGGINGFACE_OVERRIDE_WARNING)
        else:
            errors.append(
                f"Blocked unverified Hugging Face community model `{model_id}` under strict supply-chain protection. "
                "Options: (1) use Apple-signed `--local-backend apple_fm` (macOS 26+), "
                "(2) load a verified local folder via `--local-model-dir <path>`, "
                "(3) pin an audited copy with `machybrid security pin`, or "
                "(4) explicitly opt into the warning-gated override (`machybrid security allow-hf`, "
                "`--allow-huggingface-bypass`, or Settings -> Local & Security)."
            )

    return ModelAuditResult(
        allowed=len(errors) == 0,
        model_id=model_id,
        publisher_trust=trust,
        policy_applied=cfg.policy.value,
        override_used=override_used,
        warnings=warnings,
        errors=errors,
        locked_sha256_verified=locked_verified,
        files_scanned=files_scanned,
        resolved_dir=resolved_str,
    )
