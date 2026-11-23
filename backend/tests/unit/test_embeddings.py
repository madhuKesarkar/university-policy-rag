import numpy as np
import pytest

from ingestion import embed

pytestmark = pytest.mark.unit

DIM = 384  # bge-small-en-v1.5


class FakeModel:
    """Stands in for SentenceTransformer: same text in -> same vector out."""

    def __init__(self):
        self.calls = []

    def encode(self, texts, normalize_embeddings=False, show_progress_bar=True):
        self.calls.append({"texts": texts, "normalize": normalize_embeddings})
        vectors = []
        for t in texts:
            rng = np.random.default_rng(abs(hash(t)) % (2**32))
            v = rng.normal(size=DIM)
            if normalize_embeddings:
                v = v / np.linalg.norm(v)
            vectors.append(v)
        return np.array(vectors)


@pytest.fixture
def fake_model(monkeypatch):
    model = FakeModel()
    embed._get_model.cache_clear()  # the real function is cached with lru_cache
    monkeypatch.setattr(embed, "_get_model", lambda: model)
    return model


def test_query_vector_has_right_dimension(fake_model):
    assert len(embed.embed_query("late fee policy")) == DIM


def test_query_vector_is_normalised(fake_model):
    v = np.array(embed.embed_query("late fee policy"))
    assert np.isclose(np.linalg.norm(v), 1.0)


def test_query_gets_bge_instruction_prefix(fake_model):
    embed.embed_query("late fee policy")
    sent = fake_model.calls[-1]["texts"][0]
    assert sent == "Represent this sentence for searching relevant passages: late fee policy"


def test_passages_get_no_prefix(fake_model):
    embed.embed_passages(["chunk one", "chunk two"])
    assert fake_model.calls[-1]["texts"] == ["chunk one", "chunk two"]


def test_same_input_same_vector(fake_model):
    assert embed.embed_query("x") == embed.embed_query("x")


def test_returns_plain_lists_not_numpy(fake_model):
    # pgvector and JSON both need plain Python lists
    result = embed.embed_passages(["a", "b"])
    assert isinstance(result, list) and isinstance(result[0], list)
    assert len(result) == 2