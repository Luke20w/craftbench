from ..errors import RenderError

NODE_TYPES: dict[str, type] = {}


def node_type(name: str):
    """Register a Node subclass as the class for JSON objects with this `type`."""
    def register(cls):
        cls.type = name
        NODE_TYPES[name] = cls
        return cls
    return register


class Record:
    """A JSON object without a `type` (e.g. a list item): its fields become attributes."""

    def __init__(self, data: dict):
        for key, value in data.items():
            setattr(self, key, build(value))


class Node(Record):
    """A document node. Subclasses render themselves with one `to_<format>` method per output format."""

    type = ""

    def __init__(self, data: dict):
        super().__init__({k: v for k, v in data.items() if k != "type"})

    def render(self, fmt: str) -> str:
        method = getattr(self, "to_" + fmt, None)
        if method is None:
            raise RenderError(f"{self.type} nodes can't be rendered as {fmt}")
        return method()


def build(value):
    if isinstance(value, dict):
        if "type" not in value:
            return Record(value)
        cls = NODE_TYPES.get(value["type"])
        if cls is None:
            raise RenderError(f"unsupported node type: {value['type']}")
        return cls(value)
    if isinstance(value, list):
        return [build(v) for v in value]
    return value
