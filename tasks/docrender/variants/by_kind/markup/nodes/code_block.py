from ..formats import escape
from ..text import prefix_lines
from .base import Node, node_type


@node_type("code_block")
class CodeBlock(Node):
    def to_html(self) -> str:
        attr = ' class="language-' + escape(self.language, "html") + '"' if self.language else ""
        return "<pre><code" + attr + ">" + escape(self.code, "html") + "</code></pre>"

    def to_markdown(self) -> str:
        fence = "````" if "```" in self.code else "```"
        return fence + self.language + "\n" + self.code + "\n" + fence

    def to_plain(self) -> str:
        return prefix_lines(self.code, "    ")

    def to_latex(self) -> str:
        return "\\begin{verbatim}\n" + self.code + "\n\\end{verbatim}"

    def to_mediawiki(self) -> str:
        if self.language:
            return '<syntaxhighlight lang="' + self.language + '">\n' + self.code + "\n</syntaxhighlight>"
        return "<pre>\n" + escape(self.code, "mediawiki") + "\n</pre>"

    def to_bbcode(self) -> str:
        opening = "[code=" + self.language + "]" if self.language else "[code]"
        return opening + "\n" + self.code + "\n[/code]"

    def to_org(self) -> str:
        opening = "#+BEGIN_SRC " + self.language if self.language else "#+BEGIN_SRC"
        return opening + "\n" + self.code + "\n#+END_SRC"

    def to_slack(self) -> str:
        return "```\n" + self.code + "\n```"

    def to_jira(self) -> str:
        opening = "{code:" + self.language + "}" if self.language else "{code}"
        return opening + "\n" + self.code + "\n{code}"

    def to_dokuwiki(self) -> str:
        opening = "<code " + self.language + ">" if self.language else "<code>"
        return opening + "\n" + self.code + "\n</code>"

    def to_creole(self) -> str:
        return "{{{\n" + self.code + "\n}}}"

    def to_tiddlywiki(self) -> str:
        return "```" + self.language + "\n" + self.code + "\n```"
