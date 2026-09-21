# Parsers register

The libraries and the limits behind `documents.ingest`. Written by hand with the descriptor of the
capability that uses them; a new format is a new row and a new hostile sample. Every parse of bytes
runs in the bounded child (`retrieval/runner.py`): a deadline of `CAPABILITY_DOCUMENTS__TIMEOUT_MS`,
a 1 GiB address-space ceiling on POSIX, a recursion limit of 2 000, at most 64 MB answered.

| Format | Library | Why it beats the standard library | Limits (refused as) | Not parsed |
| --- | --- | --- | --- | --- |
| `docx` | `zipfile` + `defusedxml` | the standard library reads the container; `defusedxml` refuses entity expansion and DTDs, which `xml.etree` does not | ≤ 2 000 entries, ≤ 32 MB per entry, ≤ 64 MB inflated, inflation ratio ≤ 100 (`document_too_large`); macro parts, binaries, path traversal, missing `word/document.xml`, malformed XML (`document_malformed`); ≤ 5 000 blocks / 200 000 characters after parsing (`document_too_large`) | images, embedded objects, comments, tracked changes, headers and footers |
| `pptx` | `zipfile` + `defusedxml` | as `docx`; slides read in number order, the title placeholder becomes the heading | as `docx` | notes, images, embedded media |
| `pdf` | `pypdf` (pure Python, BSD) | a text-layer reader with no rendering, no JavaScript engine and no network; the alternative readers render or shell out | ≤ 20 MB (`document_too_large`), ≤ 500 pages (`document_too_large`); not `%PDF-`, `/JavaScript`, `/JS`, `/Launch`, `/OpenAction`, `/AA`, `/EmbeddedFile`, an unreadable structure (`document_malformed`) | scanned images (no OCR — a later card with a vision model row and an image budget), forms, attachments |
| `markdown` | the standard library | `#` headings become the path (six levels), fenced code stays one block, list items split | ≤ 800 KB of UTF-8, control characters refused (`document_malformed`), the text limit (`document_too_large`) | HTML inside Markdown is text |
| `text` | the standard library | paragraphs by blank lines | as `markdown` | — |

Any other declared format is `document_unsupported` before a byte is read. Extracted text inherits
the document's declared class; a RESTRICTED pattern in it refuses the document whole
(`document_restricted`). Nothing is retained but the chunks the index holds.
