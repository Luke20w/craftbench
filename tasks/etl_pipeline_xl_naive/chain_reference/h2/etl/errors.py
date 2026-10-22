"""Errors reported to the caller as {status: error, error_code, message, path}."""

class EtlError(Exception):
    problems = None   # validation errors: every step's first problem, when collected (--all-errors)

    def __init__(self, code, message, path):
        super().__init__(message)
        self.code = code
        self.path = path

def schema_error(message, path):
    return EtlError('SCHEMA_VALIDATION_FAILED', 'ETL_ERROR: ' + message, path)
