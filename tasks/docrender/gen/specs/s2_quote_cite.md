# Quote attributions

We quote customers and other docs a lot, and readers can't tell who said what. Quotes need to show their
source.

A `quote` node may now have an optional `cite` field: a list of inline nodes. When it's present and not
empty, the quote ends with an attribution: an em dash and a space (`— `) followed by the cite, rendered as
inlines usually are. The attribution goes inside the quote, after the quote's blocks, as one more block
(separated from them by a blank line, like any other block), so it gets the same prefix or wrapper as the
rest of the quote. In html it is `<footer>— …</footer>` on its own line, just before `</blockquote>`.

Quotes without `cite` render exactly as before.

{{EXAMPLE:quote_cite:rich:markdown}}

{{EXAMPLE:quote_cite:rich:html}}
