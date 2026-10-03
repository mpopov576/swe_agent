import hashlib
import shutil
import subprocess
from pathlib import Path
from tempfile import mkdtemp

import main


class FakeEmbeddingModelManager:
    def __init__(self, model_name):
        self.model_name = model_name
        self.started = False

    def start_session(self):
        self.started = True

    def stop_session(self):
        pass


class FakeEmbeddingClient:
    def __init__(self, model_manager):
        pass

    def load(self):
        pass

    def embed(self, texts):
        return [[float(b) for b in hashlib.sha256(t.encode()).digest()[:16]] for t in texts]


def make_local_repo():
    repo_path = Path(mkdtemp()) / "repo"
    repo_path.mkdir(parents=True)

    subprocess.run(["git", "init", "-q"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.email", "a@a.com"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "a"], cwd=repo_path, check=True)

    (repo_path / "users.py").write_text(
        "def create_user(name):\n    save_user(name)\n\ndef save_user(name):\n    pass\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "add", "-A"], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo_path, check=True)

    return repo_path


class FakeSandbox:
    def __init__(self, repo_path):
        self.repo_path = repo_path
        self.deleted = False

    def run_command_in_sandbox(self, command):
        return {"exit_code": 0, "stdout": "ok", "stderr": ""}

    def get_diff(self):
        return {"changed_files": "", "git_diff": ""}

    def delete_dir(self):
        self.deleted = True
        shutil.rmtree(self.repo_path.parent, ignore_errors=True)


def test_build_context_manager_indexes_and_retrieves_real_repo():
    repo_path = make_local_repo()
    sandbox = FakeSandbox(repo_path)
    storage_path = str(Path(mkdtemp()) / "chroma_store")

    original_manager = main.EmbeddingModelManager
    original_client = main.EmbeddingClient
    main.EmbeddingModelManager = FakeEmbeddingModelManager
    main.EmbeddingClient = FakeEmbeddingClient

    context_manager, embedding_model_manager = main.build_context_manager(
        sandbox, embedding_model="fake-model", storage_path=storage_path,
    )

    main.EmbeddingModelManager = original_manager
    main.EmbeddingClient = original_client

    assert embedding_model_manager.started is True

    result = context_manager.retrieve("create_user")
    assert "create_user" in result
    assert "save_user" in result

    sandbox.delete_dir()


class FakeModelManager:
    def __init__(self, agent_model, judge_model):
        self.agent_model = agent_model
        self.judge_model = judge_model

    def start_session(self):
        pass

    def stop_session(self):
        pass


class FakeVerificationLoop:
    last_instance = None

    def __init__(self, swe_agent, judge_agent, sandbox):
        self.sandbox = sandbox
        FakeVerificationLoop.last_instance = self

    def run(self, issue_text):
        return {"status": "committed", "attempt": 1}


def make_fake_sandbox_runner_class():
    repo_path = make_local_repo()

    class FakeSandboxRunner:
        def __init__(self, repo_url):
            self.repo_path = repo_path
            self.deleted = False

        def clone_repo(self):
            pass

        def run_command_in_sandbox(self, command):
            return {"exit_code": 0, "stdout": "ok", "stderr": ""}

        def get_diff(self):
            return {"changed_files": "", "git_diff": ""}

        def delete_dir(self):
            self.deleted = True

    return FakeSandboxRunner


def test_main_wires_everything_and_returns_loop_result():
    FakeSandboxRunner = make_fake_sandbox_runner_class()

    originals = {
        "ModelManager": main.ModelManager,
        "SandboxRunner": main.SandboxRunner,
        "EmbeddingModelManager": main.EmbeddingModelManager,
        "EmbeddingClient": main.EmbeddingClient,
        "VerificationLoop": main.VerificationLoop,
        "LLMClient": main.LLMClient,
    }

    main.ModelManager = FakeModelManager
    main.SandboxRunner = FakeSandboxRunner
    main.EmbeddingModelManager = FakeEmbeddingModelManager
    main.EmbeddingClient = FakeEmbeddingClient
    main.VerificationLoop = FakeVerificationLoop
    main.LLMClient = lambda model: model

    result = main.main(
        repo_url="unused",
        issue_text="fix the bug",
        agent_model="agent-model",
        judge_model="judge-model",
        embedding_model="embed-model",
    )

    for name, original in originals.items():
        setattr(main, name, original)

    assert result == {"status": "committed", "attempt": 1}

    sandbox = FakeVerificationLoop.last_instance.sandbox
    assert sandbox.deleted is True

    shutil.rmtree(sandbox.repo_path.parent, ignore_errors=True)


if __name__ == "__main__":
    test_build_context_manager_indexes_and_retrieves_real_repo()
    print("PASSED: test_build_context_manager_indexes_and_retrieves_real_repo")

    test_main_wires_everything_and_returns_loop_result()
    print("PASSED: test_main_wires_everything_and_returns_loop_result")

    print("\nAll tests passed.")