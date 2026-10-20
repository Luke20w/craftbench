"""Error type shared across the pipeline."""

SCHEMA_VALIDATION_FAILED = "SCHEMA_VALIDATION_FAILED"
UNKNOWN_OP = "UNKNOWN_OP"
MISSING_COLUMN = "MISSING_COLUMN"
BAD_EXPR = "BAD_EXPR"
EXECUTION_FAILED = "EXECUTION_FAILED"
MALFORMED_STEP = "MALFORMED_STEP"


class EtlError(Exception):
    """A user-facing error that is rendered as the JSON error response."""

    def __init__(self, code, message, path=""):
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path

    def to_response(self):
        return {
            "status": "error",
            "error_code": self.code,
            "message": f"ETL_ERROR: {self.message}",
            "path": self.path,
        }
