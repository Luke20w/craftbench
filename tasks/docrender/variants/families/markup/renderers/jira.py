from .lightweight import LineMarkup


class JiraRenderer(LineMarkup):
    subscript_marks = ("~", "~")
    superscript_marks = ("^", "^")
    highlight_marks = ("{color:#ffab00}", "{color}")
    kbd_template = "{{{{{value}}}}}"
    math_template = "{{{{{value}}}}}"
    figure_caption = "\n_{caption}_"
    strong_marks = ("*", "*")
    emphasis_marks = ("_", "_")
    code_marks = ("{{", "}}")
    link_template = "[{text}|{url}]"
    quote_wrap = ("{quote}", "{quote}")
    list_style = "stack"
    header_cells = ("||", "||", "||")
    table_cells = ("|", "|", "|")
    rule_text = "----"

    def esc(self, text: str) -> str:
        for ch in "\\*_{}[]|":
            text = text.replace(ch, "\\" + ch)
        return text

    def heading_marks(self, level: int) -> tuple[str, str]:
        return f"h{min(level, 6)}. ", ""

    def code_fence(self, language: str, code: str) -> tuple[str, str]:
        return ("{code:" + language + "}" if language else "{code}"), "{code}"

    def table_rule(self, columns: int) -> str | None:
        return None

    def image(self, node) -> str:
        return "!" + node.src + "|alt=" + node.alt + "!" if node.alt else "!" + node.src + "!"
