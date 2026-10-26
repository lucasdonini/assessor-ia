import logging


class OAuthAccessLogFilter(logging.Filter):
    """Remove authorization codes and state from Uvicorn access records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple) and len(record.args) == 5:
            address, method, path, version, status = record.args
            if isinstance(path, str) and "/google/callback" in path:
                record.args = (address, method, path.split("?", 1)[0], version, status)
        return True
