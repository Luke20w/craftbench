from .lightweight import LineMarkup


class MarkdownRenderer(LineMarkup):
    line_break_text = "\\\n"

    def esc(self, text: str) -> str:
        for ch in "\\`*_[]#|":
            text = text.replace(ch, "\\" + ch)
        return text

    def url(self, url: str) -> str:
        return url.replace(" ", "%20").replace(")", "%29")

    def code(self, node) -> str:
        if "`" in node.value:
            return "`` " + node.value + " ``"
        return "`" + node.value + "`"

    def code_fence(self, language: str, code: str) -> tuple[str, str]:
        fence = "````" if "```" in code else "```"
        return fence + language, fence
