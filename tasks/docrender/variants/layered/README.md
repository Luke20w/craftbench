# docrender

Renders a document, given as a JSON tree on stdin, to a markup format on stdout.

    python docrender.py --to markdown < doc.json

On an unknown format or node type it prints `error: ...` to stderr and exits with status 2.

## Document format

A document is `{"type": "document", "children": [blocks]}`. Every node is an object with a `type`; all
fields shown are required.

Inline nodes:

| type | fields |
|---|---|
| `text` | `value`: string |
| `strong`, `emphasis` | `children`: inlines |
| `code` | `value`: string |
| `link` | `url`: string, `children`: inlines |
| `line_break` | |
| `subscript`, `superscript`, `highlight` | `children`: inlines |
| `kbd` (a key or key combination), `math` (TeX) | `value`: string |

Block nodes:

| type | fields |
|---|---|
| `paragraph` | `children`: inlines |
| `heading` | `level`: 1–6, `children`: inlines |
| `code_block` | `language`: string (may be empty), `code`: string |
| `quote` | `children`: blocks |
| `list` | `ordered`: bool, `items`: list of `{"children": inlines, "sublist": list node or null}` |
| `table` | `header`: list of cells, `rows`: list of rows (lists of cells); a cell is a list of inlines |
| `rule` | |
| `image` | `src`: string, `alt`: string |
| `figure` | `src`: string, `alt`: string, `caption`: inlines |

Blocks are separated by a blank line (a single newline in HTML); the output ends with a newline.
