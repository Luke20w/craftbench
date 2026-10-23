# Strikethrough

Editors keep asking for a way to show text as struck through: old prices, finished to-dos, retracted
statements. Please support it.

It arrives as a new inline node, allowed anywhere inline nodes are:

```json
{"type": "strikethrough", "children": [inline nodes]}
```

The children render as usual; around them, each format puts:

| format | output |
|---|---|
| html | `<del>` … `</del>` |
| markdown | `~~` … `~~` |
| plain | `~` … `~` |
| latex | `\sout{` … `}` |
| mediawiki | `<s>` … `</s>` |
| bbcode | `[s]` … `[/s]` |
| org | `+` … `+` |
| slack | `~` … `~` |
| jira | `-` … `-` |
| dokuwiki | `<del>` … `</del>` |
| creole | `--` … `--` |
| tiddlywiki | `~~` … `~~` |

{{EXAMPLE:strikethrough:nested:markdown}}
