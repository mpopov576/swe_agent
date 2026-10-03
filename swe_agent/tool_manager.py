
class ToolManager:
    def __init__(self):
        self._tools = {}
        self._permission = {}

    def register_tool(self, name: str, handler, description: str, permission: str, parameters: dict = None):
        if name in self._tools:
            raise ValueError("Tool already registered")

        self._tools[name] = {
            "handler": handler,
            "description": description,
            "parameters": parameters or {"type": "object", "properties": {}, "required": []},
        }

        self._permission[name] = permission

    def remove_tool(self, name: str):
        if name not in self._tools:
            raise ValueError("Tool not registered")

        del self._tools[name]
        del self._permission[name]

    def get_tools(self):
        return self._tools

    def get_permissions(self):
        return self._permission

    def set_permission(self, name, permission: str):
        if name not in self._tools:
            raise ValueError("Tool not registered")

        self._permission[name] = permission

    def get_tool_schemas(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool["description"],
                    "parameters": tool["parameters"],
                },
            }
            for name, tool in self._tools.items()
            if self._permission[name] != "disabled"
        ]

    def execute_tool(self, name: str, **kwargs):
        if name not in self._tools:
            raise ValueError("Tool not registered")

        permission = self._permission[name]

        if permission == "disabled":
            raise PermissionError("Tool is disabled")

        handler = self._tools[name]["handler"]

        return handler(**kwargs)