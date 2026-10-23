from ..errors import RenderError


class Renderer:
    """Renders a node tree in one output format: one method per node type, named after it."""

    separator = "\n\n"

    def render(self, node) -> str:
        if node.type == "document":
            return self.blocks(node.children) + "\n"
        method = getattr(self, node.type, None)
        if method is None:
            raise RenderError(f"unsupported node type: {node.type}")
        return method(node)

    def inlines(self, children) -> str:
        return "".join(self.render(child) for child in children)

    def blocks(self, children) -> str:
        return self.separator.join(self.render(child) for child in children)

    def esc(self, text: str) -> str:
        return text
