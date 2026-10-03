TOOL_SCHEMAS = {
    "read_file": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path relative to the repo root",
            },
        },
        "required": ["path"],
    },
    "edit_file": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path relative to the repo root",
            },
            "old_text": {
                "type": "string",
                "description": (
                    "Exact existing text copied from the file, including "
                    "indentation. Must match once; include context if repeated."
                ),
            },
            "new_text": {
                "type": "string",
                "description": (
                    "Replacement text, including indentation. "
                    "Use an empty string to delete old_text."
                ),
            },
        },
        "required": ["path", "old_text", "new_text"],
        "additionalProperties": False,
    },
    "create_file": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path relative to the repo root",
            },
            "content": {
                "type": "string",
                "description": "Initial file content",
            },
        },
        "required": ["path"],
    },
    "list_dir": {
        "type": "object",
        "properties": {
            "directory": {
                "type": "string",
                "description": "Directory path relative to the repo root",
            },
        },
        "required": ["directory"],
    },
    "goto_line": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path relative to the repo root",
            },
            "line_number": {
                "type": "integer",
                "description": "Line number to jump to (1-indexed)",
            },
        },
        "required": ["path", "line_number"],
    },
    "search_file": {
        "type": "object",
        "properties": {
            "search_term": {
                "type": "string",
                "description": "Text to search for",
            },
            "file_path": {
                "type": "string",
                "description": "File path relative to the repo root",
            },
        },
        "required": ["search_term", "file_path"],
    },
    "search_dir": {
        "type": "object",
        "properties": {
            "search_term": {
                "type": "string",
                "description": "Text to search for",
            },
            "directory": {
                "type": "string",
                "description": "Directory path relative to the repo root",
            },
        },
        "required": ["search_term", "directory"],
    },
    "run_command_in_sandbox": {
        "type": "object",
        "properties": {
            "command": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Command to run, as a list of arguments, "
                    'e.g. ["python", "main.py"]'
                ),
            },
        },
        "required": ["command"],
    },
    "verify_fix": {
        "type": "object",
        "properties": {
            "command": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "description": (
                    "The repository's verification command as argument strings"
                ),
            },
        },
        "required": ["command"],
    },
}