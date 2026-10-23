from ..formats import escape
from .base import Node, node_type


@node_type("image")
class Image(Node):
    def to_html(self) -> str:
        return '<img src="' + escape(self.src, "html") + '" alt="' + escape(self.alt, "html") + '">'

    def to_markdown(self) -> str:
        return "![" + escape(self.alt, "markdown") + "](" + self.src.replace(" ", "%20").replace(")", "%29") + ")"

    def to_plain(self) -> str:
        return "[image: " + self.alt + "]"

    def to_latex(self) -> str:
        return "\\includegraphics{" + self.src + "}"

    def to_mediawiki(self) -> str:
        return "[[File:" + self.src + "|" + escape(self.alt, "mediawiki") + "]]"

    def to_bbcode(self) -> str:
        return '[img alt="' + self.alt.replace('"', "'") + '"]' + self.src + "[/img]"

    def to_org(self) -> str:
        caption = "#+CAPTION: " + self.alt + "\n" if self.alt else ""
        return caption + "[[" + self.src + "]]"

    def to_slack(self) -> str:
        return "<" + self.src + "|" + (self.alt or self.src) + ">"

    def to_jira(self) -> str:
        return "!" + self.src + "|alt=" + self.alt + "!" if self.alt else "!" + self.src + "!"

    def to_dokuwiki(self) -> str:
        return "{{" + self.src + "|" + self.alt + "}}"

    def to_creole(self) -> str:
        return "{{" + self.src + "|" + self.alt + "}}"

    def to_tiddlywiki(self) -> str:
        return "[img[" + self.alt + "|" + self.src + "]]" if self.alt else "[img[" + self.src + "]]"
