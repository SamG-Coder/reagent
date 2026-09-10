Do not invoke native provider tools. These are ReAgent text-protocol actions,
executed by the host only after it parses your response.
If essential evidence is missing, you may request read-only tools by returning
only this JSON shape:
`{"actions":[{"tool":"decompile","target":"0x..."}]}`.
Available tools are `decompile`, `xrefs_from`, `xrefs_to`, `struct`, `enum`,
`vtable`, `global`, `strings`, `context`, `pcode`, and `cfg`. Request only
evidence needed to resolve a concrete uncertainty.
Return that JSON object alone, without prose, markdown fences, or escaped delimiters.
