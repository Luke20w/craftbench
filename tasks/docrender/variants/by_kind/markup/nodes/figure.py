from ..formats import escape, inlines
from .base import Node, node_type


@node_type("figure")
class Figure(Node):
    def to_html(self) -> str:
        return ('<figure>\n<img src="' + escape(self.src, "html") + '" alt="' + escape(self.alt, "html") + '">\n<figcaption>' + inlines(self.caption, "html")
                + "</figcaption>\n</figure>")

    def to_markdown(self) -> str:
        return "![" + escape(self.alt, "markdown") + "](" + self.src.replace(" ", "%20").replace(")", "%29") + ")\n\n*" + inlines(self.caption, "markdown") + "*"

    def to_plain(self) -> str:
        return "[image: " + self.alt + "]\n" + inlines(self.caption, "plain")

    def to_latex(self) -> str:
        return "\\begin{figure}\n\\includegraphics{" + self.src + "}\n\\caption{" + inlines(self.caption, "latex") + "}\n\\end{figure}"

    def to_mediawiki(self) -> str:
        return "[[File:" + self.src + "|thumb|" + inlines(self.caption, "mediawiki") + "]]"

    def to_bbcode(self) -> str:
        return '[img alt="' + self.alt.replace('"', "'") + '"]' + self.src + "[/img]\n[i]" + inlines(self.caption, "bbcode") + "[/i]"

    def to_org(self) -> str:
        return "#+CAPTION: " + inlines(self.caption, "org") + "\n[[" + self.src + "]]"

    def to_slack(self) -> str:
        return "<" + self.src + "|" + (self.alt or self.src) + ">\n_" + inlines(self.caption, "slack") + "_"

    def to_jira(self) -> str:
        image = "!" + self.src + "|alt=" + self.alt + "!" if self.alt else "!" + self.src + "!"
        return image + "\n_" + inlines(self.caption, "jira") + "_"

    def to_dokuwiki(self) -> str:
        return "{{" + self.src + "|" + inlines(self.caption, "dokuwiki") + "}}"

    def to_creole(self) -> str:
        return "{{" + self.src + "|" + self.alt + "}}\n//" + inlines(self.caption, "creole") + "//"

    def to_tiddlywiki(self) -> str:
        image = "[img[" + self.alt + "|" + self.src + "]]" if self.alt else "[img[" + self.src + "]]"
        return image + "\n//" + inlines(self.caption, "tiddlywiki") + "//"
