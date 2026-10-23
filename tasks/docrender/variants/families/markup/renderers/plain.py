from ..text import prefix_lines
from .lightweight import LineMarkup


class PlainTextRenderer(LineMarkup):
    subscript_marks = ("_", "")
    superscript_marks = ("^", "")
    highlight_marks = (">>", "<<")
    kbd_template = "[{value}]"
    math_template = "{value}"
    figure_caption = "\n{caption}"
    emphasis_marks = ("_", "_")
    code_marks = ("", "")
    quote_prefix = "| "
    bullet = "* "
    numbered = "{n}) "
    rule_text = "* * *"
    image_template = "[image: {alt}]"

    def strong(self, node) -> str:
        return self.inlines(node.children).upper()

    def link(self, node) -> str:
        text = self.inlines(node.children)
        return text if text == node.url else text + " <" + node.url + ">"

    def heading(self, node) -> str:
        text = self.inlines(node.children)
        if node.level == 1:
            return text + "\n" + "=" * len(text)
        if node.level == 2:
            return text + "\n" + "-" * len(text)
        return text

    def code_block(self, node) -> str:
        return prefix_lines(node.code, "    ")

    def table(self, node) -> str:
        rows, widths = self.aligned(node)

        def line(cells):
            return " | ".join(cell.ljust(width) for cell, width in zip(cells, widths)).rstrip()
        lines = [line(rows[0]), "-+-".join("-" * width for width in widths)]
        lines += [line(cells) for cells in rows[1:]]
        return "\n".join(lines)
