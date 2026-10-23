from ..formats import escape, inlines
from .base import Node, node_type


@node_type("link")
class Link(Node):
    def to_html(self) -> str:
        return '<a href="' + escape(self.url, "html") + '">' + inlines(self.children, "html") + "</a>"

    def to_markdown(self) -> str:
        url = self.url.replace(" ", "%20").replace(")", "%29")
        return "[" + inlines(self.children, "markdown") + "](" + url + ")"

    def to_plain(self) -> str:
        text = inlines(self.children, "plain")
        return text if text == self.url else text + " <" + self.url + ">"

    def to_latex(self) -> str:
        url = self.url.replace("%", "\\%").replace("#", "\\#")
        return "\\href{" + url + "}{" + inlines(self.children, "latex") + "}"

    def to_mediawiki(self) -> str:
        return "[" + self.url + " " + inlines(self.children, "mediawiki") + "]"

    def to_bbcode(self) -> str:
        return "[url=" + self.url + "]" + inlines(self.children, "bbcode") + "[/url]"

    def to_org(self) -> str:
        return "[[" + self.url + "][" + inlines(self.children, "org") + "]]"

    def to_slack(self) -> str:
        return "<" + self.url + "|" + inlines(self.children, "slack") + ">"

    def to_jira(self) -> str:
        return "[" + inlines(self.children, "jira") + "|" + self.url + "]"

    def to_dokuwiki(self) -> str:
        return "[[" + self.url + "|" + inlines(self.children, "dokuwiki") + "]]"

    def to_creole(self) -> str:
        return "[[" + self.url + "|" + inlines(self.children, "creole") + "]]"

    def to_tiddlywiki(self) -> str:
        return "[[" + inlines(self.children, "tiddlywiki") + "|" + self.url + "]]"
