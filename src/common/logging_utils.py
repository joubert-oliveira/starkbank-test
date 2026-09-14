import logging


class _PrefixedLoggerAdapter(logging.LoggerAdapter):
    """Prepends a "[COMPONENT]" tag to every message logged through it.

    Both Lambdas share the same CloudWatch account, and the tag makes it
    possible to tell which one (or which piece) produced a given line
    without having to cross-reference log group names.
    """

    def process(self, msg, kwargs):
        return f"[{self.extra['component']}] {msg}", kwargs


def get_logger(component: str) -> logging.LoggerAdapter:
    base_logger = logging.getLogger()
    base_logger.setLevel(logging.INFO)
    return _PrefixedLoggerAdapter(base_logger, {"component": component})
