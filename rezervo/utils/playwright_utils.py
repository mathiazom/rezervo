from pathlib import Path

from rezervo.settings import get_settings

PLAYWRIGHT_TRACING = get_settings().IS_DEVELOPMENT
PLAYWRIGHT_TRACING_DIR = Path("playwright_traces")


def build_playwright_tracing_path(name: str) -> Path:
    return PLAYWRIGHT_TRACING_DIR / f"{name}.zip"


async def playwright_trace_start(context):
    if PLAYWRIGHT_TRACING:
        await context.tracing.start(screenshots=True, snapshots=True, sources=True)


async def playwright_trace_stop(context, name):
    if PLAYWRIGHT_TRACING:
        await context.tracing.stop(path=build_playwright_tracing_path(name))
