import contextlib
import json
import tempfile
from inspect import currentframe
from pathlib import Path


@contextlib.contextmanager
def aprs_ctx():
    context_manager_frame = currentframe().f_back  # intermediate decorator frame
    caller_frame = context_manager_frame.f_back
    ctx = {
        "file": caller_frame.f_code.co_filename,
        "name": caller_frame.f_code.co_name,
        "line": caller_frame.f_lineno,
        "vars": caller_frame.f_locals,
    }
    with tempfile.TemporaryDirectory() as temp_dir:
        context_dump_path = Path(temp_dir) / "context.json"
        with open(context_dump_path, "w") as f:
            f.write(json.dumps(ctx, default=str, indent=4))
        yield str(context_dump_path)
