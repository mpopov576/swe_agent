from swe_agent.context.embeddings.manager import EmbeddingModelManager
from swe_agent.context.embeddings.client import EmbeddingClient


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def test_embedding_model_manager():
    manager = EmbeddingModelManager(MODEL_NAME)

    assert manager.get_model() == MODEL_NAME

    manager.set_model("another-model")

    assert manager.get_model() == "another-model"


def test_embedding_model_cannot_change_during_session():
    manager = EmbeddingModelManager(MODEL_NAME)

    manager.start_session()

    try:
        manager.set_model("another-model")
        assert False, "Expected RuntimeError"
    except RuntimeError:
        pass

    manager.stop_session()


def test_embedding_session_lifecycle():
    manager = EmbeddingModelManager(MODEL_NAME)

    manager.start_session()

    try:
        manager.start_session()
        assert False, "Expected RuntimeError"
    except RuntimeError:
        pass

    manager.stop_session()

    try:
        manager.stop_session()
        assert False, "Expected RuntimeError"
    except RuntimeError:
        pass


def test_embedding_client_requires_model_to_be_loaded():
    manager = EmbeddingModelManager(MODEL_NAME)
    client = EmbeddingClient(manager)

    try:
        client.embed(["hello world"])
        assert False, "Expected RuntimeError"
    except RuntimeError:
        pass


def test_embedding_client_generates_embeddings():
    manager = EmbeddingModelManager(MODEL_NAME)
    client = EmbeddingClient(manager)

    client.load()

    embeddings = client.embed([
        "authentication service",
        "database connection",
    ])

    assert len(embeddings) == 2
    assert len(embeddings[0]) > 0
    assert len(embeddings[1]) == len(embeddings[0])


def test_embedding_client_same_text_same_embedding():
    manager = EmbeddingModelManager(MODEL_NAME)
    client = EmbeddingClient(manager)

    client.load()

    embeddings = client.embed([
        "authentication service",
        "authentication service",
    ])

    assert embeddings[0] == embeddings[1]


def test_embedding_client_different_text_produces_different_embedding():
    manager = EmbeddingModelManager(MODEL_NAME)
    client = EmbeddingClient(manager)

    client.load()

    embeddings = client.embed([
        "authentication service",
        "database connection",
    ])

    assert embeddings[0] != embeddings[1]


def test_embedding_client_unload():
    manager = EmbeddingModelManager(MODEL_NAME)
    client = EmbeddingClient(manager)

    client.load()
    client.unload()

    try:
        client.embed(["hello world"])
        assert False, "Expected RuntimeError"
    except RuntimeError:
        pass