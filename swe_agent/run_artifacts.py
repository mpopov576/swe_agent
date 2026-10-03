import json
from pathlib import Path
from tempfile import mkdtemp


def _serialize_extra(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")

    if isinstance(value, Path):
        return str(value)

    raise TypeError(
        "Cannot serialize an object of type "
        f"{type(value).__name__}"
    )


def save_run_result(
    result: dict,
    metadata: dict,
    output_root: Path,
):
    diff = result.get("diff")

    patch = (
        diff.get("git_diff")
        if isinstance(diff, dict)
        else None
    )

    document = {
        "metadata": metadata,
        "result": result,
    }

    result_json = json.dumps(
        document,
        indent=2,
        ensure_ascii=True,
        default=_serialize_extra,
    )

    output_root = output_root.resolve()

    output_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    run_directory = Path(
        mkdtemp(
            prefix="run-",
            dir=str(output_root),
        )
    )

    # When capture failed, save the report without creating
    # a misleading empty or incomplete patch file.
    if isinstance(patch, str):
        (run_directory / "patch.diff").write_bytes(
            patch.encode(
                "utf-8",
                errors="surrogateescape",
            )
        )

    (run_directory / "result.json").write_text(
        result_json,
        encoding="utf-8",
    )

    return run_directory