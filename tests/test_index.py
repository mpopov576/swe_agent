from swe_agent.context.index import build_index


def test_python_grammar(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir()

    file_path = repository / "example.py"
    file_path.write_text(
        "class UserService:\n"
        "    def create_user(self):\n"
        "        pass\n"
        "\n"
        "def helper():\n"
        "    return True\n",
        encoding="utf-8",
    )

    chunks = build_index(str(repository))

    names = {chunk["name"] for chunk in chunks}

    assert "UserService" in names
    assert "create_user" in names
    assert "helper" in names


def test_javascript_grammar(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir()

    file_path = repository / "example.js"
    file_path.write_text(
        "class UserService {\n"
        "    createUser() {}\n"
        "}\n"
        "\n"
        "function helper() {\n"
        "    return true;\n"
        "}\n",
        encoding="utf-8",
    )

    chunks = build_index(str(repository))

    names = {chunk["name"] for chunk in chunks}

    assert "UserService" in names
    assert "createUser" in names
    assert "helper" in names


def test_typescript_grammar(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir()

    file_path = repository / "example.ts"
    file_path.write_text(
        "class UserService {\n"
        "    createUser(): void {}\n"
        "}\n"
        "\n"
        "function helper(): boolean {\n"
        "    return true;\n"
        "}\n",
        encoding="utf-8",
    )

    chunks = build_index(str(repository))

    names = {chunk["name"] for chunk in chunks}

    assert "UserService" in names
    assert "createUser" in names
    assert "helper" in names


def test_java_grammar(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir()

    file_path = repository / "Example.java"
    file_path.write_text(
        "class UserService {\n"
        "    void createUser() {}\n"
        "}\n",
        encoding="utf-8",
    )

    chunks = build_index(str(repository))

    names = {chunk["name"] for chunk in chunks}

    assert "UserService" in names
    assert "createUser" in names


def test_c_grammar(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir()

    file_path = repository / "example.c"
    file_path.write_text(
        "int add(int a, int b) {\n"
        "    return a + b;\n"
        "}\n",
        encoding="utf-8",
    )

    chunks = build_index(str(repository))

    names = {chunk["name"] for chunk in chunks}

    assert "add" in names


def test_cpp_grammar(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir()

    file_path = repository / "example.cpp"
    file_path.write_text(
        "class Calculator {\n"
        "public:\n"
        "    int add(int a, int b) {\n"
        "        return a + b;\n"
        "    }\n"
        "};\n",
        encoding="utf-8",
    )

    chunks = build_index(str(repository))

    names = {chunk["name"] for chunk in chunks}

    assert "Calculator" in names
    assert "add" in names


def test_go_grammar(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir()

    file_path = repository / "example.go"
    file_path.write_text(
        "package main\n"
        "\n"
        "func add(a int, b int) int {\n"
        "    return a + b\n"
        "}\n",
        encoding="utf-8",
    )

    chunks = build_index(str(repository))

    names = {chunk["name"] for chunk in chunks}

    assert "add" in names


def test_rust_grammar(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir()

    file_path = repository / "example.rs"
    file_path.write_text(
        "struct UserService {}\n"
        "\n"
        "fn create_user() {\n"
        "}\n",
        encoding="utf-8",
    )

    chunks = build_index(str(repository))

    names = {chunk["name"] for chunk in chunks}

    assert "UserService" in names
    assert "create_user" in names


def test_csharp_grammar(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir()

    file_path = repository / "Example.cs"
    file_path.write_text(
        "class UserService {\n"
        "    void CreateUser() {}\n"
        "}\n",
        encoding="utf-8",
    )

    chunks = build_index(str(repository))

    names = {chunk["name"] for chunk in chunks}

    assert "UserService" in names
    assert "CreateUser" in names


def test_nested_directories(tmp_path):
    repository = tmp_path / "repository"
    nested_directory = repository / "src" / "services"
    nested_directory.mkdir(parents=True)

    file_path = nested_directory / "user.py"
    file_path.write_text(
        "def get_user():\n"
        "    return None\n",
        encoding="utf-8",
    )

    chunks = build_index(str(repository))

    assert len(chunks) == 1
    assert chunks[0]["name"] == "get_user"


def test_unsupported_files_are_ignored(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir()

    file_path = repository / "notes.txt"
    file_path.write_text(
        "hello world",
        encoding="utf-8",
    )

    chunks = build_index(str(repository))

    assert chunks == []