from .lightweight import LineMarkup


class SlackRenderer(LineMarkup):
    subscript_marks = ("", "")
    superscript_marks = ("", "")
    highlight_marks = ("*_", "_*")
    kbd_template = "`{value}`"
    math_template = "`{value}`"
    figure_caption = "\n_{caption}_"
    strong_marks = ("*", "*")
    emphasis_marks = ("_", "_")
    link_template = "<{url}|{text}>"
    bullet = "• "
    list_indent = "    "
    rule_text = "----------"

    def esc(self, text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def heading_marks(self, level: int) -> tuple[str, str]:
        return "*", "*"

    def code_fence(self, language: str, code: str) -> tuple[str, str]:
        return "```", "```"

    def table(self, node) -> str:
        rows, widths = self.aligned(node)
        lines = ["  ".join(cell.ljust(width) for cell, width in zip(cells, widths)).rstrip() for cells in rows]
        return "```\n" + "\n".join(lines) + "\n```"

    def image(self, node) -> str:
        return "<" + node.src + "|" + (node.alt or node.src) + ">"
