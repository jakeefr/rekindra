"""Rekindra native Hermes plugin. No registration-time filesystem or network IO."""
from . import handlers, schemas


def register(ctx):
    for name, handler in handlers.make_handlers(llm_factory=lambda: ctx.llm).items():
        ctx.register_tool(name=name, toolset='rekindra', schema=schemas.SCHEMAS[name], handler=handler)
