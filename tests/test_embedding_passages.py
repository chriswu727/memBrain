import os
from pathlib import Path

import pytest

from membrain.embedding_passages import token_passages
from membrain.local_embeddings import PREFIXES, LocalEmbeddingProvider, installed, runtime_available

MODEL = os.environ.get("MEMBRAIN_TEST_EMBEDDING_MODEL")
pytestmark = pytest.mark.skipif(not MODEL or not runtime_available(), reason="Pinned local embedding model required")


@pytest.fixture
def model():
    directory = installed(Path(MODEL))
    assert directory is not None
    with LocalEmbeddingProvider(directory) as provider:
        provider._load()
        yield provider


@pytest.mark.parametrize("text", [
    "My passport is in the drawer.",
    "收据整理完之后" * 500 + "护照在蓝色抽屉里",
    "I reviewed ordinary office receipts " * 180 + "my passport is in the blue drawer",
    "🧠é e\u0301 العربية 中文 " * 180 + "最後の書類",
    ' ' * 1200 + 'passport',
    '\u200b' * 1200 + 'passport',
], ids=['short', 'cjk', 'latin', 'mixed_unicode', 'whitespace', 'normalized_away'])
def test_document_windows_cover_the_original_unicode_text_without_exceeding_model_limit(model, text):
    windows = token_passages(model._document_tokenizer, text, PREFIXES['document'])
    assert windows[0].start == 0 and windows[-1].end == len(text)
    assert all(0 <= part.start < part.end <= len(text) and len(part.ids) <= 512
               and part.end - part.start <= 400 for part in windows)
    assert all(right.start <= left.end and right.end > left.end
               for left, right in zip(windows, windows[1:]))
    if len(windows) == 1:
        legacy = model._tokenizer.encode(PREFIXES['document'] + text)
        assert windows[0].ids == tuple(legacy.ids)


def test_tail_changes_are_represented_by_passages_without_changing_the_parent_head_vector(model):
    prefix = 'I spent the afternoon sorting ordinary office supplies and reviewing routine receipts ' * 70
    texts = [prefix + 'and my passport is stored in the blue kitchen drawer',
             prefix + 'and my passport is stored in the red bedroom suitcase']
    result = model.embed(texts)
    assert result.vectors[0] == result.vectors[1]
    assert result.document_index_version == model.document_index_version
    assert len(result.passages) == 2 and all(len(parts) > 1 for parts in result.passages)
    assert result.passages[0][-1].vector != result.passages[1][-1].vector
    assert all(parts[-1].end == len(text) for parts, text in zip(result.passages, texts, strict=True))
    assert result.usage['input_tokens'] > 1024
    assert model.embed(['passport'], purpose='query').passages is None


def test_short_documents_keep_one_vector_without_redundant_passage_rows(model):
    result = model.embed(['The passport is in the blue drawer.', '证件在抽屉里。'])
    assert result.passages == ((), ())
    assert len(result.vectors) == 2
    assert all(abs(sum(value * value for value in vector) - 1) < 1e-4 for vector in result.vectors)


def test_maximum_length_documents_use_bounded_inference_batches(model, monkeypatch):
    shapes = []

    def vectors(session, ids, mask):
        shapes.append(ids.shape)
        assert mask.shape == ids.shape
        return tuple((1.,) + (0.,) * 383 for _ in ids)

    monkeypatch.setattr(model, '_vectors', vectors)
    text = 'ordinary records ' * 3855
    assert 65000 < len(text.encode()) <= 65536
    result = model.embed([text, text])
    assert len(result.vectors) == 2 and len(result.passages) == 2
    assert len(shapes) > 1 and all(rows <= 32 and width <= 512 for rows, width in shapes)
    assert all(rows * width <= 4096 and rows * width ** 2 <= 1048576 for rows, width in shapes)
    assert shapes[0][0] == 2
    assert sum(rows for rows, _ in shapes) == 2 + sum(map(len, result.passages))
    assert all(parts[0].start == 0 and parts[-1].end == len(text) for parts in result.passages)
