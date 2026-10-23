from .lightweight import LineMarkup


class TiddlyWikiRenderer(LineMarkup):
    strong_marks = ("''", "''")
    emphasis_marks = ("//", "//")
    subscript_marks = (",,", ",,")
    superscript_marks = ("^^", "^^")
    highlight_marks = ("@@", "@@")
    math_template = "$${value}$$"
    link_template = "[[{text}|{url}]]"
    line_break_text = "<br>"
    quote_wrap = ("<<<", "<<<")
    list_style = "stack"
    header_cells = ("|!", "|!", "|")
    table_cells = ("|", "|", "|")
    figure_caption = "\n//{caption}//"

    def esc(self, text: str) -> str:
        if any(ch in text for ch in "'/`[]{}<>^~_$|"):
            return '"""' + text + '"""'
        return text

    def heading_marks(self, level: int) -> tuple[str, str]:
        return "!" * min(level, 6) + " ", ""

    def table_rule(self, columns: int) -> str | None:
        return None

    def image(self, node) -> str:
        return "[img[" + node.alt + "|" + node.src + "]]" if node.alt else "[img[" + node.src + "]]"
