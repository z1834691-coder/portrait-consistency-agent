"""Local-only embedding and reranking backends for RAG P0-B.

These backends receive only canonical text generated from a validated ``RagQuery``
and reviewed tool knowledge.  They never receive a photo, face vector, raw user
utterance, API key, Provider receipt, or an instruction to call a tool.  Model
downloads are opt-in; normal runtime uses local cache only and can safely fall
back to the P0-A lexical path when the weights are unavailable.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import numpy as np


class LocalModelUnavailable(RuntimeError):
    """Raised when a local model is absent or cannot be loaded safely."""


class EmbeddingBackend(Protocol):
    """Minimal local embedding contract; tests can inject a deterministic backend."""

    model_id: str
    requested_revision: str
    actual_revision: str
    backend_name: str

    @property
    def index_key(self) -> str: ...

    def encode(self, texts: Sequence[str]) -> np.ndarray: ...


class RerankerBackend(Protocol):
    """Minimal local reranker contract; scores are ranking-only, never permissions."""

    model_id: str
    requested_revision: str
    actual_revision: str
    backend_name: str

    def score(self, query: str, passages: Sequence[str]) -> np.ndarray: ...


def _stable_model_key(model_id: str, revision: str, backend_name: str) -> str:
    payload = f"{backend_name}|{model_id}|{revision}".encode()
    return hashlib.sha256(payload).hexdigest()


def _tokenize(value: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_\-]+|[\u4e00-\u9fff]+", value.casefold())


@dataclass
class BgeEmbeddingBackend:
    """CPU BGE embedding backend using only local Hugging Face model files by default."""

    model_id: str
    requested_revision: str
    cache_path: Path
    allow_model_download: bool = False
    max_length: int = 256
    backend_name: str = "bge-transformers-cpu-v1"
    actual_revision: str = field(init=False)
    _tokenizer: Any = field(default=None, init=False, repr=False)
    _model: Any = field(default=None, init=False, repr=False)
    _torch: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.actual_revision = self.requested_revision

    @property
    def index_key(self) -> str:
        return _stable_model_key(self.model_id, self.requested_revision, self.backend_name)

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 0), dtype=np.float32)
        self._load()
        assert self._tokenizer is not None
        assert self._model is not None
        assert self._torch is not None
        encoded = self._tokenizer(
            list(texts),
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        )
        with self._torch.inference_mode():
            outputs = self._model(**encoded)
            embeddings = outputs.last_hidden_state[:, 0]
            embeddings = self._torch.nn.functional.normalize(embeddings, p=2, dim=1)
        matrix = embeddings.cpu().numpy().astype(np.float32, copy=False)
        if matrix.ndim != 2 or not np.isfinite(matrix).all():
            raise LocalModelUnavailable("embedding_model_returned_invalid_vectors")
        return matrix

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer

            self.cache_path.mkdir(parents=True, exist_ok=True)
            common = {
                "cache_dir": str(self.cache_path),
                "revision": self.requested_revision,
                "local_files_only": not self.allow_model_download,
                "trust_remote_code": False,
            }
            tokenizer = AutoTokenizer.from_pretrained(self.model_id, **common)
            model = AutoModel.from_pretrained(self.model_id, **common)
            model.to("cpu")
            model.eval()
        except Exception as exc:  # pragma: no cover - exact model-provider errors vary by host
            raise LocalModelUnavailable("embedding_model_unavailable") from exc
        self._torch = torch
        self._tokenizer = tokenizer
        self._model = model
        self.actual_revision = str(
            getattr(model.config, "_commit_hash", None) or self.requested_revision
        )


@dataclass
class BgeRerankerBackend:
    """CPU BGE cross-encoder reranker using local model weights by default."""

    model_id: str
    requested_revision: str
    cache_path: Path
    allow_model_download: bool = False
    max_length: int = 384
    backend_name: str = "bge-cross-encoder-cpu-v1"
    actual_revision: str = field(init=False)
    _tokenizer: Any = field(default=None, init=False, repr=False)
    _model: Any = field(default=None, init=False, repr=False)
    _torch: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.actual_revision = self.requested_revision

    def score(self, query: str, passages: Sequence[str]) -> np.ndarray:
        if not passages:
            return np.empty((0,), dtype=np.float32)
        self._load()
        assert self._tokenizer is not None
        assert self._model is not None
        assert self._torch is not None
        encoded = self._tokenizer(
            [query] * len(passages),
            list(passages),
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        )
        with self._torch.inference_mode():
            logits = self._model(**encoded, return_dict=True).logits.view(-1).float()
        scores = logits.cpu().numpy().astype(np.float32, copy=False)
        if scores.ndim != 1 or len(scores) != len(passages) or not np.isfinite(scores).all():
            raise LocalModelUnavailable("reranker_model_returned_invalid_scores")
        return scores

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            self.cache_path.mkdir(parents=True, exist_ok=True)
            common = {
                "cache_dir": str(self.cache_path),
                "revision": self.requested_revision,
                "local_files_only": not self.allow_model_download,
                "trust_remote_code": False,
            }
            tokenizer = AutoTokenizer.from_pretrained(self.model_id, **common)
            model = AutoModelForSequenceClassification.from_pretrained(self.model_id, **common)
            model.to("cpu")
            model.eval()
        except Exception as exc:  # pragma: no cover - exact model-provider errors vary by host
            raise LocalModelUnavailable("reranker_model_unavailable") from exc
        self._torch = torch
        self._tokenizer = tokenizer
        self._model = model
        self.actual_revision = str(
            getattr(model.config, "_commit_hash", None) or self.requested_revision
        )


@dataclass
class DeterministicTokenEmbeddingBackend:
    """Small offline test backend; never used as the P0-B production default."""

    model_id: str = "fixture-token-embedder"
    requested_revision: str = "fixture-v1"
    actual_revision: str = "fixture-v1"
    backend_name: str = "deterministic-token-v1"
    dimension: int = 64

    @property
    def index_key(self) -> str:
        return _stable_model_key(self.model_id, self.requested_revision, self.backend_name)

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        rows: list[np.ndarray] = []
        for value in texts:
            vector = np.zeros(self.dimension, dtype=np.float32)
            for token in _tokenize(value):
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                index = int.from_bytes(digest[:4], "big") % self.dimension
                vector[index] += -1.0 if digest[4] % 2 else 1.0
            norm = float(np.linalg.norm(vector))
            rows.append(vector / norm if norm else vector)
        return (
            np.vstack(rows).astype(np.float32)
            if rows
            else np.empty((0, self.dimension), np.float32)
        )


@dataclass
class TokenOverlapReranker:
    """Deterministic test reranker that makes ordering assertions offline."""

    model_id: str = "fixture-token-reranker"
    requested_revision: str = "fixture-v1"
    actual_revision: str = "fixture-v1"
    backend_name: str = "token-overlap-v1"

    def score(self, query: str, passages: Sequence[str]) -> np.ndarray:
        query_tokens = set(_tokenize(query))
        scores = [float(len(query_tokens & set(_tokenize(passage)))) for passage in passages]
        return np.asarray(scores, dtype=np.float32)
