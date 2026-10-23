# Callouts

Our docs need callout boxes, the "Note:" / "Warning:" / "Tip:" panels people put around important
paragraphs. Right now writers fake them with quotes and they come out inconsistently.

They arrive as a new block node, allowed anywhere block nodes are:

```json
{"type": "callout", "variant": "note" | "warning" | "tip", "children": [block nodes]}
```

Below, BLOCKS is the children rendered and separated as blocks normally are in that format; `variant`,
`Variant` and `VARIANT` are the variant in lower case, capitalized and upper case. "On its own line" means
separated from what follows by a newline.

| format | output |
|---|---|
| html | `<aside class="callout variant">` on its own line, BLOCKS, then a newline and `</aside>` |
| markdown | a quote whose first line is `[!VARIANT]`, followed by BLOCKS: every line prefixed with `> ` (a bare `>` on empty lines), as quotes are |
| plain | `VARIANT:` on its own line, then BLOCKS with every line indented by two spaces (empty lines stay empty) |
| latex | `\begin{variant}`, BLOCKS and `\end{variant}`, each on its own line |
| mediawiki | `{{Variant\|1=`, BLOCKS and `}}`, each on its own line |
| bbcode | `[quote=Variant]`, BLOCKS and `[/quote]`, each on its own line |
| org | `#+BEGIN_VARIANT`, BLOCKS and `#+END_VARIANT`, each on its own line |
| slack | a quote (every line prefixed with `> `, a bare `>` on empty lines) whose first line is the icon, a space and `*Variant*`, followed by BLOCKS. Icons: note `:information_source:`, warning `:warning:`, tip `:bulb:` |
| jira | `{panel:title=Variant}`, BLOCKS and `{panel}`, each on its own line |
| dokuwiki | `<WRAP variant>`, BLOCKS and `</WRAP>`, each on its own line |
| creole | a quote (every line prefixed with `> `, a bare `>` on empty lines) whose first line is `VARIANT:`, followed by BLOCKS |
| tiddlywiki | `@@.variant`, BLOCKS and `@@`, each on its own line |

{{EXAMPLE:callout:warning:markdown}}

{{EXAMPLE:callout:warning:plain}}
