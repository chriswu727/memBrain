"""What an embedding is: its space, request and result. The only provider is the local model
(``local_embeddings.LocalEmbeddingProvider``); the metered remote provider was removed."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol

from .helpers import digest


def _bounded_integer(value, name, minimum=1, maximum=2**31 - 1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be a bounded integer")
    return value


def _name(value, name):
    if (not isinstance(value, str) or not value.strip() or len(value) > 256
            or any(ord(character) < 32 for character in value)):
        raise ValueError(f"{name} must be explicitly configured")
    return value


@dataclass(frozen=True)
class EmbeddingSpace:
    model: str
    model_version: str
    dimensions: int

    def __post_init__(self):
        _name(self.model, "model")
        _name(self.model_version, "model_version")
        _bounded_integer(self.dimensions, "dimensions", maximum=65536)

    def descriptor(self) -> dict[str, str | int]:
        return asdict(self)

    @property
    def fingerprint(self) -> str:
        return digest(self.descriptor())


@dataclass(frozen=True)
class EmbeddingRequest:
    texts: tuple[str, ...]
    timeout_seconds: float = 10.0
    purpose: str = "document"  # "query" for search text; providers without asymmetric encoders ignore it


@dataclass(frozen=True)
class EmbeddingPassage:
    start: int
    end: int
    vector: tuple[float, ...]


@dataclass(frozen=True)
class EmbeddingResult:
    space: EmbeddingSpace
    vectors: tuple[tuple[float, ...], ...]
    usage: dict[str, int | None] | None
    request_fingerprint: str
    input_bytes: int
    passages: tuple[tuple[EmbeddingPassage, ...], ...] | None = None
    document_index_version: str = "single-vector-v1"


class EmbeddingProvider(Protocol):
    @property
    def space(self) -> EmbeddingSpace: ...

    def __call__(self, request: EmbeddingRequest) -> EmbeddingResult: ...

    def embed(self, texts: list[str] | tuple[str, ...], *, timeout_seconds: float = 10.0) -> EmbeddingResult: ...
