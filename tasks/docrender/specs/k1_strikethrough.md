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

For example, this document:

```json
{"type": "document", "children": [{"type": "paragraph", "children": [{"type": "strikethrough", "children": [{"type": "text", "value": "old "}, {"type": "strong", "children": [{"type": "text", "value": "bold"}]}, {"type": "text", "value": " text"}]}, {"type": "text", "value": " and "}, {"type": "emphasis", "children": [{"type": "strikethrough", "children": [{"type": "text", "value": "gone"}]}]}]}]}
```

renders with `--to markdown` as:

````
~~old **bold** text~~ and *~~gone~~*
````
