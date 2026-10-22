class K85X(Exception):
    def __init__(self, q8v, q4j, q85x):
        super().__init__(q4j)
        self.q8v = q8v
        self.q85x = q85x


def q57x(q4j, q85x):
    return K85X('SCHEMA_VALIDATION_FAILED', 'ETL_ERROR: ' + q4j, q85x)
