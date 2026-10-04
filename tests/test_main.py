import inspect

import main


def test_main_entrypoint_is_callable():
    assert callable(main.main)


def test_main_entrypoint_has_required_inputs():
    signature = inspect.signature(
        main.main
    )

    parameters = signature.parameters

    assert "repo_url" in parameters
    assert "issue_text" in parameters


def test_main_entrypoint_exposes_model_configuration():
    signature = inspect.signature(
        main.main
    )

    parameters = signature.parameters

    assert "agent_model" in parameters
    assert "judge_model" in parameters
    assert "embedding_model" in parameters


def test_main_entrypoint_supports_approval_callback():
    signature = inspect.signature(
        main.main
    )

    parameters = signature.parameters

    assert "approval_callback" in parameters