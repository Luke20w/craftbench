from .bbcode import BBCodeRenderer
from .creole import CreoleRenderer
from .dokuwiki import DokuWikiRenderer
from .html import HtmlRenderer
from .jira import JiraRenderer
from .latex import LatexRenderer
from .markdown import MarkdownRenderer
from .mediawiki import MediaWikiRenderer
from .org import OrgRenderer
from .plain import PlainTextRenderer
from .slack import SlackRenderer
from .tiddlywiki import TiddlyWikiRenderer

RENDERERS = {
    "html": HtmlRenderer,
    "markdown": MarkdownRenderer,
    "plain": PlainTextRenderer,
    "latex": LatexRenderer,
    "mediawiki": MediaWikiRenderer,
    "bbcode": BBCodeRenderer,
    "org": OrgRenderer,
    "slack": SlackRenderer,
    "jira": JiraRenderer,
    "dokuwiki": DokuWikiRenderer,
    "creole": CreoleRenderer,
    "tiddlywiki": TiddlyWikiRenderer,
}
