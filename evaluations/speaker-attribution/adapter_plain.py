"""Plain-retrieval baseline: the raw stored messages, ranked for the question, filling the same budget.

Every stored turn, user and assistant alike, is ranked by reciprocal-rank fusion of BM25 and cosine similarity under
memBrain's pinned local embedding model (the ranking of ``evaluations/locomo/retrieval_recall.py``). Turns are taken
in rank order while they fit the budget, then shown oldest first. There are no notes, no history block and no
speaker rule: it is the plain alternative at equal size.

Two forms, both real ways of keeping raw messages:

- ``plain`` writes each turn with its role, ``[user] ...`` or ``[assistant] ...``.
- ``plain-unlabelled`` (``roles=False``) writes the text alone, as the LongMemEval baseline in this repository
  stored it.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from kit import Line, Session, Turn

WORD = re.compile(r"[a-z0-9]+")
TURN_CHARACTERS = 700  # What memBrain shows of one long message at most; no turn in the kit is longer.
_LABEL = re.compile(r"^\[(user|assistant)\] ")


class PlainRetrieval:
    def __init__(self, model_cache: Path | None, *, roles: bool = True):
        self.roles = roles
        self.name = "plain" if roles else "plain-unlabelled"
        self.provider = None
        if model_cache is not None:
            from membrain.local_embeddings import LocalEmbeddingProvider, installed

            directory = installed(Path(model_cache))
            if directory is None:
                raise RuntimeError("The embedding model is not in the model cache; run the memBrain arm first or "
                                   "pass --no-embeddings.")
            self.provider = LocalEmbeddingProvider(directory, threads=2)
        self._cache: dict[str, list[float]] = {}
        self.turns: list[Turn] = []

    # The adapter contract -------------------------------------------------------------------------------------------

    def reset(self, workdir: Path) -> None:
        self.turns = []
        self._vectors = None

    def ingest(self, session: Session) -> None:
        self.turns.extend(session.turns)

    def ready(self) -> None:
        self.tokens = [WORD.findall(turn.text.lower()) for turn in self.turns]
        self.frequency = Counter(word for tokens in self.tokens for word in set(tokens))
        self.average = sum(map(len, self.tokens)) / max(1, len(self.tokens))
        self._vectors = self._embed([turn.text[:1500] for turn in self.turns], "document") if self.provider else None

    def context(self, question: str, *, budget: int) -> str:
        chosen, used = [], 0
        for index in self.rank(question):
            line = self.render(self.turns[index])
            if used + len(line) + 1 > budget:
                continue
            chosen.append(index)
            used += len(line) + 1
        return "\n".join(self.render(self.turns[index]) for index in sorted(chosen))

    def attribute(self, context: str) -> list[Line]:
        lines = []
        for raw in context.splitlines():
            label = _LABEL.match(raw) if self.roles else None
            lines.append(Line(label.group(1) if label else None, raw))
        return lines

    def close(self) -> None:
        pass

    # Ranking --------------------------------------------------------------------------------------------------------

    def render(self, turn: Turn) -> str:
        text = " ".join(turn.text.split())[:TURN_CHARACTERS]
        return f"[{turn.role}] {text}" if self.roles else text

    def _embed(self, texts: list[str], purpose: str):
        import numpy

        vectors = []
        for start in range(0, len(texts), 32):
            batch = texts[start:start + 32]
            missing = [text for text in batch if (purpose, text) not in self._cache]
            if missing:
                result = self.provider.embed(missing, timeout_seconds=120.0, purpose=purpose)
                self._cache.update({(purpose, text): vector for text, vector in zip(missing, result.vectors)})
            vectors.extend(self._cache[(purpose, text)] for text in batch)
        matrix = numpy.asarray(vectors, dtype="float32")
        return matrix / numpy.maximum(numpy.linalg.norm(matrix, axis=1, keepdims=True), 1e-9)

    def _bm25(self, query: str) -> list[int]:
        words, total = WORD.findall(query.lower()), len(self.turns)
        scores = []
        for tokens in self.tokens:
            counts, score = Counter(tokens), 0.0
            for word in words:
                if counts[word]:
                    idf = math.log(1 + (total - self.frequency[word] + 0.5) / (self.frequency[word] + 0.5))
                    score += idf * counts[word] * 2.2 / (counts[word] + 1.2 * (0.25 + 0.75 * len(tokens) / self.average))
            scores.append(score)
        return sorted(range(total), key=lambda index: (-scores[index], index))

    def rank(self, query: str) -> list[int]:
        lexical = self._bm25(query)
        if self._vectors is None:
            return lexical
        scores = self._vectors @ self._embed([query], "query")[0]
        semantic = sorted(range(len(self.turns)), key=lambda index: (-float(scores[index]), index))
        fused = defaultdict(float)
        for order in (lexical, semantic):
            for position, index in enumerate(order):
                fused[index] += 1.0 / (60 + position)
        return sorted(fused, key=lambda index: (-fused[index], index))
