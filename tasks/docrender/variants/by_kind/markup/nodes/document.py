from ..formats import blocks
from .base import Node, node_type


@node_type("document")
class Document(Node):
    def render(self, fmt: str) -> str:
        return blocks(self.children, fmt) + "\n"
