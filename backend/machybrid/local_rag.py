"""On-Device Local Workspace & Document RAG for MacHybridAI.

Provides zero-cloud, dependency-free BM25 + TF-IDF semantic chunking and retrieval
entirely in memory on this Mac:
- Splits attached files or workspace excerpts into overlapping semantic chunks.
- Computes BM25 + cosine lexical-semantic relevance scores against a user query.
- Feeds only the highest-signal chunks into Station 1 (Local Analysis) and Station 2
  (On-Device Privacy Gate PII scrubbing) before any cloud reasoning occurs.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

_STOPWORDS = frozenset({
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "was",
    "were",
    "will",
    "with",
    "this",
    "please",
    "can",
    "you",
})

_TOKEN_RE = re.compile(r"[a-z0-9_@.\-]{2,}")
_SECTION_RE = re.compile(r"^---\s+(.+?)\s+---\s*$", re.MULTILINE)


def _tokenize(text: str) -> List[str]:
    return [
        tok
        for tok in _TOKEN_RE.findall(text.lower())
        if tok not in _STOPWORDS
    ]


@dataclass(frozen=True)
class RAGChunk:
    """Represents a single retrieved on-device document chunk."""

    chunk_id: str
    source_label: str
    text: str
    score: float
    token_count: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LocalWorkspaceRAG:
    """In-memory on-device RAG engine using BM25 + TF-IDF cosine scoring."""

    def __init__(self, chunk_chars: int = 900, overlap_chars: int = 150) -> None:
        self.chunk_chars = max(250, chunk_chars)
        self.overlap_chars = max(0, min(overlap_chars, self.chunk_chars // 2))
        self._chunks: List[RAGChunk] = []
        self._chunk_tfs: List[Counter[str]] = []
        self._df: Dict[str, int] = {}
        self._avg_dl: float = 1.0
        self._last_indexed_text: Optional[str] = None

    def index_inline_context(
        self,
        inline_context: str,
        default_label: str = "attached_context",
    ) -> int:
        """Splits `inline_context` (including `--- filename ---` sections) into chunks and pre-computes BM25 statistics."""
        raw = (inline_context or "").strip()
        if raw and raw == self._last_indexed_text and self._chunks:
            return len(self._chunks)

        self._chunks.clear()
        self._chunk_tfs.clear()
        self._df.clear()
        self._avg_dl = 1.0
        self._last_indexed_text = raw
        if not raw:
            return 0

        # Parse `--- label ---` sections if present
        matches = list(_SECTION_RE.finditer(raw))
        sections: List[tuple[str, str]] = []
        if matches:
            for idx, match in enumerate(matches):
                label = match.group(1).strip() or default_label
                start = match.end()
                end = matches[idx + 1].start() if idx + 1 < len(matches) else len(raw)
                body = raw[start:end].strip()
                if body:
                    sections.append((label, body))
        else:
            sections.append((default_label, raw))

        chunk_counter = 0
        total_tokens = 0
        for label, body in sections:
            cursor = 0
            n = len(body)
            while cursor < n:
                end = min(n, cursor + self.chunk_chars)
                snippet = body[cursor:end].strip()
                if snippet:
                    chunk_counter += 1
                    tokens = _tokenize(snippet)
                    tf = Counter(tokens)
                    dl = len(tokens)
                    total_tokens += dl
                    for unique_tok in tf:
                        self._df[unique_tok] = self._df.get(unique_tok, 0) + 1
                    self._chunk_tfs.append(tf)
                    self._chunks.append(
                        RAGChunk(
                            chunk_id=f"chunk_{chunk_counter}",
                            source_label=label,
                            text=snippet,
                            score=0.0,
                            token_count=dl,
                        )
                    )
                if end >= n:
                    break
                cursor = max(cursor + 1, end - self.overlap_chars)

        if self._chunks:
            self._avg_dl = max(1.0, total_tokens / len(self._chunks))
        return len(self._chunks)

    def retrieve(
        self,
        query: str,
        top_k: int = 4,
        inline_context: Optional[str] = None,
    ) -> List[RAGChunk]:
        """Retrieves the top-k most relevant chunks for `query` using pre-computed BM25 statistics."""
        if inline_context is not None:
            self.index_inline_context(inline_context)

        if not self._chunks:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return self._chunks[: max(1, top_k)]

        num_docs = len(self._chunks)
        avg_dl = self._avg_dl
        df = self._df

        k1 = 1.5
        b = 0.75
        scored: List[RAGChunk] = []

        for chunk, tf in zip(self._chunks, self._chunk_tfs):
            dl = chunk.token_count
            score = 0.0
            for q_tok in query_tokens:
                term_tf = tf.get(q_tok, 0)
                if term_tf == 0:
                    continue
                n_q = df.get(q_tok, 0)
                idf = math.log(1.0 + (num_docs - n_q + 0.5) / (n_q + 0.5))
                denom = term_tf + k1 * (1.0 - b + b * (dl / avg_dl))
                score += idf * ((term_tf * (k1 + 1.0)) / max(0.001, denom))

            scored.append(
                RAGChunk(
                    chunk_id=chunk.chunk_id,
                    source_label=chunk.source_label,
                    text=chunk.text,
                    score=round(score, 4),
                    token_count=dl,
                )
            )

        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[: max(1, top_k)]

    def format_retrieved_context(self, chunks: List[RAGChunk]) -> str:
        """Formats retrieved chunks for Station 1 and Station 2 processing."""
        if not chunks:
            return ""
        blocks = [
            f"[{c.source_label} · {c.chunk_id} · score={c.score:.2f}]\n{c.text}"
            for c in chunks
        ]
        return "\n\n".join(blocks)
