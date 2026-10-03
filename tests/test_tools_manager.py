from swe_agent.tool_manager import ToolManager


def test_register_tool():
    manager = ToolManager()

    def test_tool():
        return "hello"

    manager.register_tool(
        name="test_tool",
        handler=test_tool,
        description="A test tool",
        permission="read",
    )

    assert "test_tool" in manager.get_tools()
    assert manager.get_tools()["test_tool"]["description"] == "A test tool"
    assert manager.get_permissions()["test_tool"] == "read"


def test_execute_tool():
    manager = ToolManager()

    def add(a, b):
        return a + b

    manager.register_tool(
        name="add",
        handler=add,
        description="Add two numbers",
        permission="execute",
    )

    assert manager.execute_tool("add", a=2, b=3) == 5


def test_remove_tool():
    manager = ToolManager()

    def test_tool():
        return "hello"

    manager.register_tool(
        name="test_tool",
        handler=test_tool,
        description="A test tool",
        permission="read",
    )

    manager.remove_tool("test_tool")

    assert "test_tool" not in manager.get_tools()
    assert "test_tool" not in manager.get_permissions()


def test_cannot_register_duplicate_tool():
    manager = ToolManager()

    def test_tool():
        return "hello"

    manager.register_tool(
        name="test_tool",
        handler=test_tool,
        description="A test tool",
        permission="read",
    )

    try:
        manager.register_tool(
            name="test_tool",
            handler=test_tool,
            description="Another tool",
            permission="read",
        )
        assert False
    except ValueError:
        pass


def test_disabled_tool_cannot_execute():
    manager = ToolManager()

    def test_tool():
        return "hello"

    manager.register_tool(
        name="test_tool",
        handler=test_tool,
        description="A test tool",
        permission="read",
    )

    manager.set_permission("test_tool", "disabled")

    try:
        manager.execute_tool("test_tool")
        assert False
    except PermissionError:
        pass


def test_set_permission():
    manager = ToolManager()

    def test_tool():
        return "hello"

    manager.register_tool(
        name="test_tool",
        handler=test_tool,
        description="A test tool",
        permission="read",
    )

    manager.set_permission("test_tool", "write")

    assert manager.get_permissions()["test_tool"] == "write"


if __name__ == "__main__":
    test_register_tool()
    test_execute_tool()
    test_remove_tool()
    test_cannot_register_duplicate_tool()
    test_disabled_tool_cannot_execute()
    test_set_permission()

    print("All ToolManager tests passed.")