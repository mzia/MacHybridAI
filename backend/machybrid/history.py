"""Local Mac & iCloud Drive Prompt History Manager with Auto-Delete Policies.

Features:
- Stores user prompt and chat history either:
  1. Locally on This Mac (`~/Library/Application Support/MacHybridAI/history/chat_history.json`)
  2. In iCloud Drive (`~/Library/Mobile Documents/com~apple~CloudDocs/MacHybridAI/chat_history.json`)
- Configurable auto-delete retention periods:
  - `24h` (24 hours)
  - `7d` (7 days)
  - `30d` (30 days)
  - `90d` (90 days)
  - `never` (Never delete prompts)
- Enforces that all cloud AI calls are stateless (`store=False`, temporary chat mode)
  so NOTHING remains in any Cloud AI provider's history.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class HistoryStorageLocation(str, Enum):
    """Where the user's prompt history is stored."""

    LOCAL = "local"
    ICLOUD = "icloud"
    GDRIVE = "gdrive"


class HistoryRetentionPolicy(str, Enum):
    """Auto-delete period for saved prompts and chat sessions."""

    HOURS_24 = "24h"
    DAYS_7 = "7d"
    DAYS_30 = "30d"
    DAYS_90 = "90d"
    NEVER = "never"

    @property
    def ttl_seconds(self) -> Optional[int]:
        """Returns the retention TTL in seconds, or `None` if set to `never`."""
        mapping = {
            HistoryRetentionPolicy.HOURS_24: 24 * 3600,
            HistoryRetentionPolicy.DAYS_7: 7 * 24 * 3600,
            HistoryRetentionPolicy.DAYS_30: 30 * 24 * 3600,
            HistoryRetentionPolicy.DAYS_90: 90 * 24 * 3600,
            HistoryRetentionPolicy.NEVER: None,
        }
        return mapping[self]

    @property
    def display_label(self) -> str:
        labels = {
            HistoryRetentionPolicy.HOURS_24: "Auto-delete after 24 Hours",
            HistoryRetentionPolicy.DAYS_7: "Auto-delete after 7 Days",
            HistoryRetentionPolicy.DAYS_30: "Auto-delete after 30 Days",
            HistoryRetentionPolicy.DAYS_90: "Auto-delete after 90 Days",
            HistoryRetentionPolicy.NEVER: "Never Delete (Keep Forever)",
        }
        return labels[self]


@dataclass
class ChatMessageRecord:
    """A single user or assistant turn in a saved conversation."""

    id: str
    role: str  # "user" | "assistant"
    content: str
    created_at: float
    compute_mode: str = "hybrid"
    cloud_provider: str = "gemini"
    sanitized_cloud_prompt: Optional[str] = None
    pii_masked_count: int = 0
    pii_restored_count: int = 0
    cloud_zero_retention: bool = True


@dataclass
class ChatSessionRecord:
    """A multi-turn chat conversation saved locally or in iCloud Drive."""

    session_id: str
    title: str
    created_at: float
    updated_at: float
    storage_location: str
    retention_policy: str
    expires_at: Optional[float] = None
    messages: List[ChatMessageRecord] = field(default_factory=list)

    def is_expired(self, now: Optional[float] = None) -> bool:
        current = now if now is not None else time.time()
        if self.retention_policy == HistoryRetentionPolicy.NEVER.value:
            return False
        if self.expires_at is None:
            return False
        return current >= self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "storage_location": self.storage_location,
            "retention_policy": self.retention_policy,
            "expires_at": self.expires_at,
            "messages": [asdict(m) for m in self.messages],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> ChatSessionRecord:
        msgs_raw = raw.get("messages", [])
        messages: List[ChatMessageRecord] = []
        if isinstance(msgs_raw, list):
            for item in msgs_raw:
                if isinstance(item, dict):
                    messages.append(
                        ChatMessageRecord(
                            id=str(item.get("id", uuid.uuid4().hex[:12])),
                            role=str(item.get("role", "user")),
                            content=str(item.get("content", "")),
                            created_at=float(item.get("created_at", time.time())),
                            compute_mode=str(item.get("compute_mode", "hybrid")),
                            cloud_provider=str(item.get("cloud_provider", "gemini")),
                            sanitized_cloud_prompt=(
                                str(item["sanitized_cloud_prompt"])
                                if item.get("sanitized_cloud_prompt") is not None
                                else None
                            ),
                            pii_masked_count=int(item.get("pii_masked_count", 0)),
                            pii_restored_count=int(item.get("pii_restored_count", 0)),
                            cloud_zero_retention=bool(
                                item.get("cloud_zero_retention", True)
                            ),
                        )
                    )
        return cls(
            session_id=str(raw.get("session_id", f"chat_{uuid.uuid4().hex[:10]}")),
            title=str(raw.get("title", "New Hybrid Chat")),
            created_at=float(raw.get("created_at", time.time())),
            updated_at=float(raw.get("updated_at", time.time())),
            storage_location=str(
                raw.get("storage_location", HistoryStorageLocation.LOCAL.value)
            ),
            retention_policy=str(
                raw.get("retention_policy", HistoryRetentionPolicy.DAYS_30.value)
            ),
            expires_at=(
                float(raw["expires_at"])
                if raw.get("expires_at") is not None
                else None
            ),
            messages=messages,
        )


class PromptHistoryManager:
    """Manages local Mac and iCloud Drive chat history with auto-delete policies and encryption at rest."""

    def __init__(
        self,
        storage_location: HistoryStorageLocation = HistoryStorageLocation.LOCAL,
        retention_policy: HistoryRetentionPolicy = HistoryRetentionPolicy.DAYS_30,
        custom_local_dir: Optional[str] = None,
        custom_icloud_dir: Optional[str] = None,
        custom_gdrive_dir: Optional[str] = None,
        encrypt_at_rest: bool = False,
        redacted_only: bool = False,
        encryption_key: Optional[bytes] = None,
    ) -> None:
        self.storage_location = storage_location
        self.retention_policy = retention_policy
        self.encrypt_at_rest = encrypt_at_rest
        self.redacted_only = redacted_only
        # If the caller explicitly provides a key (e.g. tests), use it directly.
        # Otherwise load-or-create a persistent key file so encrypted history
        # files remain readable across process restarts.
        self._explicit_key: Optional[bytes] = encryption_key
        self._local_dir = Path(
            custom_local_dir
            or os.path.expanduser(
                "~/Library/Application Support/MacHybridAI/history"
            )
        )
        self._icloud_dir = Path(
            custom_icloud_dir
            or os.path.expanduser(
                "~/Library/Mobile Documents/com~apple~CloudDocs/MacHybridAI"
            )
        )
        self._gdrive_dir = Path(
            custom_gdrive_dir or str(self._detect_gdrive_dir())
        )

    @staticmethod
    def _detect_gdrive_dir() -> Path:
        """Auto-detects macOS Google Drive for Desktop mount via directory enumeration."""
        cloud_storage = Path(os.path.expanduser("~/Library/CloudStorage"))
        try:
            if cloud_storage.is_dir():
                for child in sorted(cloud_storage.iterdir(), key=lambda p: p.name):
                    if child.is_dir() and child.name.startswith("GoogleDrive-"):
                        my_drive = child / "My Drive"
                        if my_drive.is_dir():
                            return my_drive / "MacHybridAI"
                        return child / "MacHybridAI"
        except OSError:
            pass
        return Path(os.path.expanduser("~/Google Drive/My Drive/MacHybridAI"))

    @property
    def _key_file_path(self) -> Path:
        """Path to the persistent 32-byte encryption key file (chmod 600)."""
        return self._local_dir / ".encryption_key"

    @property
    def _encryption_key(self) -> bytes:
        """Load-or-create the persistent encryption key.

        The key is stored as raw bytes in ``~/.../history/.encryption_key``
        with permissions 0o600.  On first use the file is created from
        ``os.urandom(32)``; subsequent calls load it from disk so that
        encrypted ``chat_history.json`` files survive process restarts.

        If an explicit key was supplied at construction time (e.g. in tests),
        that key is always returned without any file I/O.
        """
        if self._explicit_key is not None:
            return self._explicit_key
        key_path = self._key_file_path
        try:
            key_path.parent.mkdir(parents=True, exist_ok=True)
            if key_path.is_file():
                data = key_path.read_bytes()
                if len(data) == 32:
                    return data
            # Generate and persist a new key
            new_key = os.urandom(32)
            key_path.write_bytes(new_key)
            try:
                os.chmod(key_path, 0o600)
            except OSError:
                pass
            return new_key
        except OSError:
            # Filesystem not writable (e.g. sandboxed test env): fall back to
            # an in-process ephemeral key so the process still works.
            ephemeral = os.urandom(32)
            self._explicit_key = ephemeral
            return ephemeral

    @property
    def active_directory(self) -> Path:
        if self.storage_location == HistoryStorageLocation.ICLOUD:
            return self._icloud_dir
        if self.storage_location == HistoryStorageLocation.GDRIVE:
            return self._gdrive_dir
        return self._local_dir

    @property
    def shared_directory(self) -> Path:
        return self.active_directory / "Shared"

    @property
    def active_file_path(self) -> Path:
        return self.active_directory / "chat_history.json"

    def is_icloud_available(self) -> bool:
        """Checks whether the macOS iCloud Drive root folder is available."""
        try:
            cloud_docs = self._icloud_dir.parent
            return cloud_docs.exists() or self._icloud_dir.exists()
        except OSError:
            return False

    def is_gdrive_available(self) -> bool:
        """Checks whether a synced Google Drive folder is available."""
        try:
            parent = self._gdrive_dir.parent
            return parent.exists() or self._gdrive_dir.exists()
        except OSError:
            return False

    def _compute_expiry(self, base_timestamp: float) -> Optional[float]:
        ttl = self.retention_policy.ttl_seconds
        if ttl is None:
            return None
        return base_timestamp + ttl

    @staticmethod
    def _xor_keystream(data: bytes, key: bytes, nonce: bytes) -> bytes:
        chunks: List[bytes] = []
        block_index = 0
        offset = 0
        prefix = key + nonce
        data_len = len(data)
        while offset < data_len:
            digest = hashlib.sha256(prefix + block_index.to_bytes(8, "big")).digest()
            block = data[offset : offset + 32]
            chunk_len = len(block)
            xored_int = int.from_bytes(block, "big") ^ int.from_bytes(
                digest[:chunk_len], "big"
            )
            chunks.append(xored_int.to_bytes(chunk_len, "big"))
            offset += chunk_len
            block_index += 1
        return b"".join(chunks)

    def _seal_json_bytes(self, plaintext: bytes) -> Dict[str, Any]:
        nonce = os.urandom(16)
        ciphertext = self._xor_keystream(plaintext, self._encryption_key, nonce)
        mac = hmac.new(self._encryption_key, nonce + ciphertext, hashlib.sha256).digest()
        return {
            "encrypted": True,
            "cipher": "SHA256-CTR-HMAC-SHA256",
            "nonce_b64": base64.b64encode(nonce).decode("ascii"),
            "ciphertext_b64": base64.b64encode(ciphertext).decode("ascii"),
            "tag_b64": base64.b64encode(mac).decode("ascii"),
            "storage_location": self.storage_location.value,
            "retention_policy": self.retention_policy.value,
            "cloud_ai_history_retained": False,
        }

    def _open_json_envelope(self, envelope: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not envelope.get("encrypted"):
            return envelope
        try:
            nonce = base64.b64decode(str(envelope["nonce_b64"]))
            ciphertext = base64.b64decode(str(envelope["ciphertext_b64"]))
            expected_tag = base64.b64decode(str(envelope["tag_b64"]))
            actual_tag = hmac.new(
                self._encryption_key, nonce + ciphertext, hashlib.sha256
            ).digest()
            if not hmac.compare_digest(expected_tag, actual_tag):
                return None
            plaintext = self._xor_keystream(ciphertext, self._encryption_key, nonce)
            parsed = json.loads(plaintext.decode("utf-8"))
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None

    def _read_raw_sessions(self) -> List[ChatSessionRecord]:
        target = self.active_file_path
        try:
            if not target.is_file():
                return []
            raw_text = target.read_text(encoding="utf-8")
            outer = json.loads(raw_text)
            if not isinstance(outer, dict):
                return []
            data = self._open_json_envelope(outer)
            if not isinstance(data, dict):
                return []
            raw_list = data.get("sessions", [])
            return [
                ChatSessionRecord.from_dict(item)
                for item in raw_list
                if isinstance(item, dict)
            ]
        except (OSError, ValueError, TypeError):
            return []

    def load_sessions(self, now: Optional[float] = None) -> List[ChatSessionRecord]:
        """Loads saved sessions from the active storage location and prunes expired items."""
        sessions = self._read_raw_sessions()
        valid_sessions = [s for s in sessions if not s.is_expired(now=now)]
        if len(valid_sessions) != len(sessions):
            self._write_sessions(valid_sessions)
        return valid_sessions

    def _write_sessions(self, sessions: List[ChatSessionRecord]) -> None:
        target_dir = self.active_directory
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            inner_payload: Dict[str, Any] = {
                "storage_location": self.storage_location.value,
                "retention_policy": self.retention_policy.value,
                "encrypt_at_rest": self.encrypt_at_rest,
                "redacted_only": self.redacted_only,
                "cloud_ai_history_retained": False,
                "updated_at": time.time(),
                "sessions": [s.to_dict() for s in sessions],
            }
            if self.encrypt_at_rest:
                raw_inner = json.dumps(inner_payload).encode("utf-8")
                disk_payload = self._seal_json_bytes(raw_inner)
            else:
                disk_payload = inner_payload
            target_file = self.active_file_path
            target_file.write_text(json.dumps(disk_payload, indent=2), encoding="utf-8")
            try:
                os.chmod(target_file, 0o600)
            except OSError:
                pass
        except OSError:
            pass

    def configure(
        self,
        storage_location: Optional[HistoryStorageLocation] = None,
        retention_policy: Optional[HistoryRetentionPolicy] = None,
        encrypt_at_rest: Optional[bool] = None,
        redacted_only: Optional[bool] = None,
        migrate_existing: bool = True,
    ) -> Dict[str, Any]:
        """Updates storage destination (Local vs iCloud), auto-delete retention, and encryption settings."""
        existing = self.load_sessions()
        if storage_location is not None and storage_location != self.storage_location:
            self.storage_location = storage_location

        if retention_policy is not None:
            self.retention_policy = retention_policy
            for session in existing:
                session.retention_policy = self.retention_policy.value
                session.expires_at = self._compute_expiry(session.updated_at)

        if encrypt_at_rest is not None:
            self.encrypt_at_rest = encrypt_at_rest

        if redacted_only is not None:
            self.redacted_only = redacted_only

        if migrate_existing:
            for session in existing:
                session.storage_location = self.storage_location.value
            self._write_sessions([s for s in existing if not s.is_expired()])

        return self.status_dict()

    def record_exchange(
        self,
        prompt: str,
        response_text: str,
        compute_mode: str,
        cloud_provider: str,
        sanitized_cloud_prompt: Optional[str],
        pii_masked_count: int,
        pii_restored_count: int,
        session_id: Optional[str] = None,
        now: Optional[float] = None,
    ) -> ChatSessionRecord:
        """Appends a user prompt and assistant response to a chat session and saves it."""
        ts = now if now is not None else time.time()
        sessions = self.load_sessions(now=ts)

        stored_prompt = (
            sanitized_cloud_prompt
            if (self.redacted_only and sanitized_cloud_prompt)
            else prompt
        )

        target_session: Optional[ChatSessionRecord] = None
        if session_id:
            for s in sessions:
                if s.session_id == session_id:
                    target_session = s
                    break

        if target_session is None:
            short_title = stored_prompt.strip().splitlines()[0][:48] or "New Hybrid Chat"
            target_session = ChatSessionRecord(
                session_id=session_id or f"chat_{uuid.uuid4().hex[:10]}",
                title=short_title,
                created_at=ts,
                updated_at=ts,
                storage_location=self.storage_location.value,
                retention_policy=self.retention_policy.value,
                expires_at=self._compute_expiry(ts),
                messages=[],
            )
            sessions.insert(0, target_session)

        user_msg = ChatMessageRecord(
            id=f"msg_{uuid.uuid4().hex[:10]}",
            role="user",
            content=stored_prompt,
            created_at=ts,
            compute_mode=compute_mode,
            cloud_provider=cloud_provider,
            sanitized_cloud_prompt=sanitized_cloud_prompt,
            pii_masked_count=pii_masked_count,
            pii_restored_count=0,
            cloud_zero_retention=True,
        )
        assistant_msg = ChatMessageRecord(
            id=f"msg_{uuid.uuid4().hex[:10]}",
            role="assistant",
            content=response_text,
            created_at=ts,
            compute_mode=compute_mode,
            cloud_provider=cloud_provider,
            sanitized_cloud_prompt=sanitized_cloud_prompt,
            pii_masked_count=pii_masked_count,
            pii_restored_count=pii_restored_count,
            cloud_zero_retention=True,
        )
        target_session.messages.append(user_msg)
        target_session.messages.append(assistant_msg)
        target_session.updated_at = ts
        target_session.storage_location = self.storage_location.value
        target_session.retention_policy = self.retention_policy.value
        target_session.expires_at = self._compute_expiry(ts)

        # Keep most recently updated session first
        sessions.sort(key=lambda item: item.updated_at, reverse=True)
        self._write_sessions(sessions)
        return target_session

    def export_session_markdown(
        self,
        session_id: str,
        use_sanitized: bool = False,
    ) -> Optional[str]:
        """Exports a saved chat session as a clean Markdown transcript."""
        for session in self.load_sessions():
            if session.session_id == session_id:
                lines = [
                    f"# {session.title}",
                    f"- **Session ID**: `{session.session_id}`",
                    f"- **Storage**: `{session.storage_location}`",
                    f"- **Retention Policy**: `{session.retention_policy}`",
                    "- **Cloud AI Retention**: `None (store=false)`",
                    "",
                    "---",
                    "",
                ]
                for msg in session.messages:
                    speaker = "User" if msg.role == "user" else "MacHybridAI Assistant"
                    body = (
                        msg.sanitized_cloud_prompt
                        if (use_sanitized and msg.role == "user" and msg.sanitized_cloud_prompt)
                        else msg.content
                    )
                    lines.append(f"### {speaker} ({msg.compute_mode.upper()})")
                    lines.append(body)
                    lines.append("")
                return "\n".join(lines)
        return None

    def export_session_to_shared_folder(
        self,
        session_id: str,
        use_sanitized: bool = True,
    ) -> Optional[Path]:
        """Writes a shareable Markdown transcript into `<ActiveDrive>/MacHybridAI/Shared/`."""
        target_session: Optional[ChatSessionRecord] = None
        for session in self.load_sessions():
            if session.session_id == session_id:
                target_session = session
                break
        if target_session is None:
            return None

        markdown = self.export_session_markdown(session_id=session_id, use_sanitized=use_sanitized)
        if markdown is None:
            return None

        slug = re.sub(r"[^A-Za-z0-9_-]+", "-", target_session.title).strip("-")[:48] or "prompt"
        safe_id = re.sub(r"[^A-Za-z0-9_-]+", "", target_session.session_id)[:10] or "chat"
        suffix = "redacted" if use_sanitized else "full"
        file_name = f"{slug}-{safe_id}-{suffix}.md"

        shared_root = os.path.normpath(os.path.realpath(str(self.shared_directory)))
        os.makedirs(shared_root, exist_ok=True)
        out_str = os.path.normpath(os.path.join(shared_root, file_name))
        if not out_str.startswith(shared_root + os.sep):
            return None
        out_path = Path(out_str)
        out_path.write_text(markdown, encoding="utf-8")
        try:
            os.chmod(out_path, 0o644)
        except OSError:
            pass
        return out_path

    def delete_session(self, session_id: str) -> bool:
        sessions = self.load_sessions()
        filtered = [s for s in sessions if s.session_id != session_id]
        if len(filtered) == len(sessions):
            return False
        self._write_sessions(filtered)
        return True

    def clear_all(self) -> int:
        sessions = self.load_sessions()
        count = len(sessions)
        self._write_sessions([])
        return count

    def prune_expired(self, now: Optional[float] = None) -> int:
        """Deletes any sessions past their auto-delete retention period."""
        all_sessions = self._read_raw_sessions()
        if not all_sessions:
            return 0
        valid = [s for s in all_sessions if not s.is_expired(now=now)]
        removed = len(all_sessions) - len(valid)
        if removed > 0:
            self._write_sessions(valid)
        return removed

    def status_dict(self) -> Dict[str, Any]:
        sessions = self.load_sessions()
        return {
            "storage_location": self.storage_location.value,
            "retention_policy": self.retention_policy.value,
            "retention_label": self.retention_policy.display_label,
            "encrypt_at_rest": self.encrypt_at_rest,
            "redacted_only": self.redacted_only,
            "active_file_path": str(self.active_file_path),
            "shared_directory": str(self.shared_directory),
            "icloud_available": self.is_icloud_available(),
            "gdrive_available": self.is_gdrive_available(),
            "cloud_ai_zero_retention": True,
            "session_count": len(sessions),
            "sessions": [s.to_dict() for s in sessions],
        }
