from .lightweight import LineMarkup


class CreoleRenderer(LineMarkup):
    emphasis_marks = ("//", "//")
    code_marks = ("{{{", "}}}")
    subscript_marks = (",,", ",,")
    superscript_marks = ("^^", "^^")
    highlight_marks = ("__", "__")
    kbd_template = "{{{{{{{value}}}}}}}"
    math_template = "{{{{{{{value}}}}}}}"
    link_template = "[[{url}|{text}]]"
    line_break_text = "\\\\"
    list_style = "stack"
    header_cells = ("|=", "|=", "|")
    table_cells = ("|", "|", "|")
    rule_text = "----"
    image_template = "{{{{{src}|{alt}}}}}"
    figure_caption = "\n//{caption}//"

    def esc(self, text: str) -> str:
        for ch in "~*/[]{}\\|=#":
            text = text.replace(ch, "~" + ch)
        return text

    def heading_marks(self, level: int) -> tuple[str, str]:
        return "=" * min(level, 6) + " ", ""

    def code_fence(self, language: str, code: str) -> tuple[str, str]:
        return "{{{", "}}}"

    def table_rule(self, columns: int) -> str | None:
        return None
