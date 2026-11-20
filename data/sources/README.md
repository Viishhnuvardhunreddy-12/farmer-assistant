# Trusted sources

Put the vetted documents for the MVP crop here (PDF, TXT or MD): agricultural
university crop guides, state agriculture department advisories, ICAR / KVK
package-of-practices documents, pesticide label recommendations.

**A file is only indexed if it is listed in `sources.json`.** That manifest is the
record of what was reviewed and approved. Copy `sources.example.json` to
`sources.json` and add one entry per file:

```json
{
  "paddy_package_of_practices_2025.pdf": {
    "title": "Paddy Package of Practices 2025",
    "publisher": "State Agricultural University",
    "url": "https://...",
    "reviewed_by": "name of the expert who approved it",
    "reviewed_on": "2026-11-20"
  }
}
```

Then run `python scripts/ingest.py`. Re-run it whenever a file changes.
Scanned PDFs without a text layer produce no text; OCR them first.
