# Trusted sources

Put the vetted documents for the MVP crop here (PDF, TXT or MD): agricultural
university crop guides, state agriculture department advisories, ICAR / KVK
package-of-practices documents, pesticide label recommendations.

**A file is only indexed if it is listed in `sources.json`.** That manifest is the
record of what was reviewed and approved. Copy `sources.example.json` to
`sources.json` and add one entry per file:

```json
{
  "chilli_package_of_practices_2025.pdf": {
    "crop": "chilli",
    "title": "Chilli Package of Practices 2025",
    "publisher": "State Agricultural University",
    "url": "https://...",
    "reviewed_by": "name of the expert who approved it",
    "reviewed_on": "2026-11-20"
  }
}
```

`crop` must match `CROP` in `.env`; documents for other crops stay listed but are not
indexed. Leave `crop` out only for documents that apply to every crop.

Then run `python scripts/ingest.py`. Re-run it whenever a file changes.

**Text and Markdown files:** start each section with a `## ` heading that names the
topic, for example `## Rice disease: Blast (cause, spread and management)`. The
heading is repeated in every chunk of its section, and when any part of a section
matches a question the whole section is retrieved, so treatment advice is found even
when the farmer only describes symptoms.

**Skip PDF pages with no advice** (cover, foreword, contents, blank forms) with
`"skip_pages": [1, 2, 3]` in the document's entry; they otherwise crowd out the useful pages.

**Check PDFs before listing them.** Scanned PDFs often come out with garbled numbers
(for example `t0` for `10`, `s00` for `500`). Never index a document whose dose
tables did not extract cleanly; type the needed sections into a `.md` file instead
and have an expert check it.

Source documents are git-ignored (they are third-party material); only this README,
`sources.json` and the example are committed.
Scanned PDFs without a text layer produce no text; OCR them first.
