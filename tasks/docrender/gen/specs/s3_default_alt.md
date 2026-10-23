# Images without alt text

Many of our images come from an upload tool that doesn't ask for alt text, so those documents leave `alt`
out entirely, and the program fails on them. Accessibility reviews also flag the empty spots.

The `alt` field of `image` and `figure` nodes is now optional. When it is missing, use the file name from
`src` (everything after the last `/`, or all of `src` if it has no `/`) as the alt text, everywhere the
format writes alt text, exactly as if the document had given that alt. An `alt` that is present, even an
empty one, is used as given.

{{EXAMPLE:default_alt:image:markdown}}

{{EXAMPLE:default_alt:image:org}}
