"""Langfuse tracing: one trace per /ask request, with spans for retrieval and generation, plus
scores (confidence, answered) for the dashboard in step 7. Fully optional — if LANGFUSE_PUBLIC_KEY
isn't set, every function here is a no-op, so the app works identically without a Langfuse
account (you just don't get traces). This matters because I can't create a Langfuse account on
your behalf; the app must degrade gracefully until you add your own free-tier keys.
"""
from contextlib import contextmanager
from functools import lru_cache

from app.config import settings


@lru_cache(maxsize=1)
def _get_client():
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return None
    from langfuse import Langfuse

    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )


def is_enabled() -> bool:
    return _get_client() is not None


@contextmanager
def trace_ask(question: str, user_id: str, role: str):
    """Yields a tracer object with .span(), .generation(), .score(), .update() helpers that are
    all no-ops when Langfuse isn't configured, so callers never need an `if enabled` check."""
    client = _get_client()
    if client is None:
        yield _NullTracer()
        return

    trace = client.trace(name="ask", user_id=user_id, input={"question": question, "role": role})
    try:
        yield _LangfuseTracer(trace)
    finally:
        client.flush()  # local/dev process: flush synchronously so traces show up immediately


class _LangfuseTracer:
    def __init__(self, trace):
        self._trace = trace

    def span(self, name: str, input=None, output=None, metadata=None):
        self._trace.span(name=name, input=input, output=output, metadata=metadata).end()

    def generation(self, name: str, model: str, input=None, output=None, usage=None):
        self._trace.generation(name=name, model=model, input=input, output=output, usage=usage).end()

    def score(self, name: str, value, comment: str | None = None):
        self._trace.score(name=name, value=value, comment=comment)

    def update(self, output=None, metadata=None):
        self._trace.update(output=output, metadata=metadata)


class _NullTracer:
    def span(self, *args, **kwargs):
        pass

    def generation(self, *args, **kwargs):
        pass

    def score(self, *args, **kwargs):
        pass

    def update(self, *args, **kwargs):
        pass
