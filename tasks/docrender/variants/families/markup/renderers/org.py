from .lightweight import LineMarkup


class OrgRenderer(LineMarkup):
    subscript_marks = ("_{", "}")
    superscript_marks = ("^{", "}")
    highlight_marks = ("@@html:<mark>@@", "@@html:</mark>@@")
    kbd_template = "={value}="
    math_template = "\\({value}\\)"
    strong_marks = ("*", "*")
    emphasis_marks = ("/", "/")
    code_marks = ("~", "~")
    link_template = "[[{url}][{text}]]"
    line_break_text = "\\\\\n"
    quote_wrap = ("#+BEGIN_QUOTE", "#+END_QUOTE")
    rule_text = "-----"

    def esc(self, text: str) -> str:
        return text.replace("[[", "[​[")

    def heading_marks(self, level: int) -> tuple[str, str]:
        return "*" * level + " ", ""

    def code_fence(self, language: str, code: str) -> tuple[str, str]:
        return ("#+BEGIN_SRC " + language if language else "#+BEGIN_SRC"), "#+END_SRC"

    def table_rule(self, columns: int) -> str | None:
        return "|" + "+".join("---" for _ in range(columns)) + "|"

    def image(self, node) -> str:
        caption = "#+CAPTION: " + node.alt + "\n" if node.alt else ""
        return caption + "[[" + node.src + "]]"

    def figure(self, node) -> str:
        return "#+CAPTION: " + self.inlines(node.caption) + "\n[[" + node.src + "]]"
