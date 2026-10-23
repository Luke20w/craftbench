# Quote attributions

We quote customers and other docs a lot, and readers can't tell who said what. Quotes need to show their
source.

A `quote` node may now have an optional `cite` field: a list of inline nodes. When it's present and not
empty, the quote ends with an attribution: an em dash and a space (`— `) followed by the cite, rendered as
inlines usually are. The attribution goes inside the quote, after the quote's blocks, as one more block
(separated from them by a blank line, like any other block), so it gets the same prefix or wrapper as the
rest of the quote. In html it is `<footer>— …</footer>` on its own line, just before `</blockquote>`.

Quotes without `cite` render exactly as before.

For example, this document:

```json
{"type": "document", "children": [{"type": "quote", "children": [{"type": "paragraph", "children": [{"type": "text", "value": "It just works."}]}, {"type": "list", "ordered": false, "items": [{"children": [{"type": "text", "value": "fast"}], "sublist": null}, {"children": [{"type": "text", "value": "small"}], "sublist": null}]}], "cite": [{"type": "strong", "children": [{"type": "text", "value": "A happy user"}]}, {"type": "text", "value": ", "}, {"type": "emphasis", "children": [{"type": "text", "value": "2026"}]}]}]}
```

renders with `--to markdown` as:

````
> It just works.
>
> - fast
> - small
>
> — **A happy user**, *2026*
````

For example, this document:

```json
{"type": "document", "children": [{"type": "quote", "children": [{"type": "paragraph", "children": [{"type": "text", "value": "It just works."}]}, {"type": "list", "ordered": false, "items": [{"children": [{"type": "text", "value": "fast"}], "sublist": null}, {"children": [{"type": "text", "value": "small"}], "sublist": null}]}], "cite": [{"type": "strong", "children": [{"type": "text", "value": "A happy user"}]}, {"type": "text", "value": ", "}, {"type": "emphasis", "children": [{"type": "text", "value": "2026"}]}]}]}
```

renders with `--to html` as:

````
<blockquote>
<p>It just works.</p>
<ul>
<li>fast</li>
<li>small</li>
</ul>
<footer>— <strong>A happy user</strong>, <em>2026</em></footer>
</blockquote>
````
