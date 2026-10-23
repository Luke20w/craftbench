# Definition lists

Our glossary pages are written as bullet lists with bold terms, and they render poorly everywhere. We'd like
real definition lists: a term, then its definition.

They arrive as a new block node, allowed anywhere block nodes are:

```json
{"type": "definition_list", "items": [{"term": [inline nodes], "definition": [block nodes]}, ...]}
```

Below, TERM is the term's inlines rendered as usual and DEF is the definition's blocks rendered and
separated as blocks normally are in that format. Each entry is rendered as shown, and entries are joined
with a newline (a blank line in markdown).

| format | one entry | the whole list |
|---|---|---|
| html | `<dt>TERM</dt>`, newline, `<dd>DEF</dd>` | `<dl>`, newline, the entries, newline, `</dl>` |
| markdown | TERM, newline, DEF with `: ` before its first line and two spaces before every other non-empty line | entries joined with a blank line |
| plain | TERM, newline, DEF with every non-empty line indented by four spaces | |
| latex | `\item[TERM] DEF`, with every non-empty line indented by two spaces | `\begin{description}`, newline, the entries, newline, `\end{description}` |
| mediawiki | `; TERM`, newline, DEF with every line prefixed with `: ` (a bare `:` on empty lines) | |
| bbcode | `[b]TERM[/b]`, newline, `[indent]DEF[/indent]` | |
| org | `- TERM :: DEF`, with two spaces before every later non-empty line | |
| slack | `*TERM*`, newline, DEF with every non-empty line indented by four spaces | |
| jira | `*TERM*`, newline, DEF | |
| dokuwiki | `  * **TERM**: DEF`, with four spaces before every later non-empty line | |
| creole | `;TERM`, newline, DEF with every line prefixed with `:` | |
| tiddlywiki | `; TERM`, newline, DEF with every line prefixed with `: ` (a bare `:` on empty lines) | |

{{EXAMPLE:definition_list:rich:markdown}}

{{EXAMPLE:definition_list:rich:latex}}
