import contextlib
import json
import tempfile
from inspect import currentframe
from pathlib import Path


@contextlib.contextmanager
def aprs_ctx():
    current_frame = currentframe()
    # intermediate decorator frame
    context_manager_frame = current_frame.f_back if current_frame is not None else None
    caller_frame = (
        context_manager_frame.f_back if context_manager_frame is not None else None
    )
    ctx = (
        {
            "file": caller_frame.f_code.co_filename,
            "name": caller_frame.f_code.co_name,
            "line": caller_frame.f_lineno,
            "vars": caller_frame.f_locals,
        }
        if caller_frame is not None
        else {}
    )
    with tempfile.TemporaryDirectory() as temp_dir:
        context_dump_path = Path(temp_dir) / "context.json"
        with open(context_dump_path, "w") as f:
            f.write(json.dumps(ctx, default=str, indent=4))
        yield str(context_dump_path)
