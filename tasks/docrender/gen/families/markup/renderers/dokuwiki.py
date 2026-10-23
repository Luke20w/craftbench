from .lightweight import LineMarkup


class DokuWikiRenderer(LineMarkup):
    highlight_marks = ("<color black/yellow>", "</color>")
    kbd_template = "<key>{value}</key>"
    strong_marks = ("**", "**")
    emphasis_marks = ("//", "//")
    code_marks = ("''", "''")
    link_template = "[[{url}|{text}]]"
    line_break_text = "\\\\ "
    bullet = "  * "
    numbered = "  - "
    list_indent = "  "
    header_cells = ("^ ", " ^ ", " ^")
    rule_text = "----"
    image_template = "{{{{{src}|{alt}}}}}"

    def esc(self, text: str) -> str:
        if any(ch in text for ch in "*/[]_'^|<>{}"):
            return "%%" + text + "%%"
        return text

    def heading_marks(self, level: int) -> tuple[str, str]:
        marks = "=" * (7 - min(level, 5))
        return marks + " ", " " + marks

    def code_fence(self, language: str, code: str) -> tuple[str, str]:
        return ("<code " + language + ">" if language else "<code>"), "</code>"

    def table_rule(self, columns: int) -> str | None:
        return None

    def figure(self, node) -> str:
        return "{{" + node.src + "|" + self.inlines(node.caption) + "}}"
