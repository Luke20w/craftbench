class Node:
    """A parsed JSON object: its fields become attributes, nested objects become Nodes."""

    def __init__(self, data: dict):
        for key, value in data.items():
            setattr(self, key, build(value))


def build(value):
    if isinstance(value, dict):
        return Node(value)
    if isinstance(value, list):
        return [build(v) for v in value]
    return value
