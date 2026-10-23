from .html import HtmlRenderer
from .markdown import MarkdownRenderer
from .plain import PlainTextRenderer
from .latex import LatexRenderer
from .mediawiki import MediaWikiRenderer
from .bbcode import BBCodeRenderer
from .org import OrgRenderer
from .slack import SlackRenderer
from .jira import JiraRenderer
from .dokuwiki import DokuWikiRenderer
from .creole import CreoleRenderer
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
