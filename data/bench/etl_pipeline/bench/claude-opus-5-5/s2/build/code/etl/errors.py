"""Error type shared by every stage of the pipeline."""

SCHEMA_VALIDATION_FAILED = "SCHEMA_VALIDATION_FAILED"
UNKNOWN_OP = "UNKNOWN_OP"
MISSING_COLUMN = "MISSING_COLUMN"
BAD_EXPR = "BAD_EXPR"
EXECUTION_FAILED = "EXECUTION_FAILED"
MALFORMED_STEP = "MALFORMED_STEP"

MESSAGE_PREFIX = "ETL_ERROR: "


class EtlError(Exception):
    """A user-facing failure, rendered as the JSON error response."""

    def __init__(self, code, detail, path=""):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.path = path

    def to_response(self):
        return {
            "status": "error",
            "error_code": self.code,
            "message": MESSAGE_PREFIX + self.detail,
            "path": self.path,
        }
