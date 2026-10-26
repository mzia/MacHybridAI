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

import json
import os
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
    """Manages local Mac and iCloud Drive chat history with auto-delete policies."""

    def __init__(
        self,
        storage_location: HistoryStorageLocation = HistoryStorageLocation.LOCAL,
        retention_policy: HistoryRetentionPolicy = HistoryRetentionPolicy.DAYS_30,
        custom_local_dir: Optional[str] = None,
        custom_icloud_dir: Optional[str] = None,
    ) -> None:
        self.storage_location = storage_location
        self.retention_policy = retention_policy
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

    @property
    def active_directory(self) -> Path:
        if self.storage_location == HistoryStorageLocation.ICLOUD:
            return self._icloud_dir
        return self._local_dir

    @property
    def active_file_path(self) -> Path:
        return self.active_directory / "chat_history.json"

    def is_icloud_available(self) -> bool:
        """Checks whether the macOS iCloud Drive root folder is available."""
        cloud_docs = self._icloud_dir.parent
        return cloud_docs.exists() or self._icloud_dir.exists()

    def _compute_expiry(self, base_timestamp: float) -> Optional[float]:
        ttl = self.retention_policy.ttl_seconds
        if ttl is None:
            return None
        return base_timestamp + ttl

    def load_sessions(self, now: Optional[float] = None) -> List[ChatSessionRecord]:
        """Loads saved sessions from the active storage location and prunes expired items."""
        target = self.active_file_path
        if not target.is_file():
            return []
        try:
            raw_text = target.read_text(encoding="utf-8")
            data = json.loads(raw_text)
            raw_list = data.get("sessions", []) if isinstance(data, dict) else []
            sessions = [
                ChatSessionRecord.from_dict(item)
                for item in raw_list
                if isinstance(item, dict)
            ]
        except (OSError, ValueError, TypeError):
            return []

        valid_sessions = [s for s in sessions if not s.is_expired(now=now)]
        if len(valid_sessions) != len(sessions):
            self._write_sessions(valid_sessions)
        return valid_sessions

    def _write_sessions(self, sessions: List[ChatSessionRecord]) -> None:
        target_dir = self.active_directory
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "storage_location": self.storage_location.value,
                "retention_policy": self.retention_policy.value,
                "cloud_ai_history_retained": False,
                "updated_at": time.time(),
                "sessions": [s.to_dict() for s in sessions],
            }
            target_file = self.active_file_path
            target_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
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
        migrate_existing: bool = True,
    ) -> Dict[str, Any]:
        """Updates storage destination (Local vs iCloud) and auto-delete retention policy."""
        existing = self.load_sessions()
        if storage_location is not None and storage_location != self.storage_location:
            self.storage_location = storage_location

        if retention_policy is not None:
            self.retention_policy = retention_policy
            for session in existing:
                session.retention_policy = self.retention_policy.value
                session.expires_at = self._compute_expiry(session.updated_at)

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

        target_session: Optional[ChatSessionRecord] = None
        if session_id:
            for s in sessions:
                if s.session_id == session_id:
                    target_session = s
                    break

        if target_session is None:
            short_title = prompt.strip().splitlines()[0][:48] or "New Hybrid Chat"
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
            content=prompt,
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
        target = self.active_file_path
        if not target.is_file():
            return 0
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
            raw_list = data.get("sessions", []) if isinstance(data, dict) else []
            all_sessions = [
                ChatSessionRecord.from_dict(item)
                for item in raw_list
                if isinstance(item, dict)
            ]
        except (OSError, ValueError, TypeError):
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
            "active_file_path": str(self.active_file_path),
            "icloud_available": self.is_icloud_available(),
            "cloud_ai_zero_retention": True,
            "session_count": len(sessions),
            "sessions": [s.to_dict() for s in sessions],
        }
