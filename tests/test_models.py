from swe_agent.model_manager import ModelManager
from swe_agent.llm_client import LLMClient


TEST_MODEL = "qwen3:8b"


def test_model_requirements():
    manager = ModelManager(TEST_MODEL, TEST_MODEL)

    requirements = manager.get_model_requirements(TEST_MODEL)

    assert requirements["parameter_count"] is not None
    assert requirements["parameter_size"] is not None
    assert requirements["quantization"] is not None


def test_check_resources():
    manager = ModelManager(TEST_MODEL, TEST_MODEL)

    resources = manager.check_resources()

    assert resources["ram_total"] > 0
    assert resources["ram_available"] > 0


def test_can_load():
    manager = ModelManager(TEST_MODEL, TEST_MODEL)

    assert manager.can_load(TEST_MODEL)


def test_model_session():
    manager = ModelManager(TEST_MODEL, TEST_MODEL)

    manager.start_session()

    assert manager._active_session is True

    manager.stop_session()

    assert manager._active_session is False


def test_llm_client():
    client = LLMClient(TEST_MODEL)

    response = client.chat([
        {
            "role": "user",
            "content": "Reply with exactly: hello",
        }
    ])

    assert response.message.content