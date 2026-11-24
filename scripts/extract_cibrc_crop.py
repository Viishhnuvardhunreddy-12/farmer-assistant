"""Extract one crop's rows from the CIB&RC "Major Uses of Pesticides" PDFs into a text source.

Download the current lists from https://ppqs.gov.in/divisions/cib-rc/major-uses-of-pesticides
into data/sources/raw/, then:

    python scripts/extract_cibrc_crop.py data/sources/raw/cibrc_mup_*.pdf

Writes data/sources/cibrc_approved_uses_<crop>.md (one "## " section per product) and
data/sources/raw/cibrc_skipped_rows_<crop>.txt. Only rows whose columns match the table
layout exactly are kept; anything irregular (shifted cells, rows split across pages) is
skipped and listed for an expert to check by hand, because a dose read from the wrong
column is worse than none.
"""

import argparse
import re
from pathlib import Path

import _bootstrap  # noqa: F401
import pdfplumber

from app.config import ROOT, get_settings

# Second-column meaning per list; the four value columns are the same in every list.
SUBJECT = {
    "insecticides": "Pest",
    "bioinsecticides": "Pest",
    "fungicides": "Disease",
    "biofungicides": "Disease",
    "herbicides": "Weeds",
    "pgr": "Time of application / purpose",
}
PRODUCT_MARKERS = re.compile(r"%|g/l|strain|accession", re.I)


def kind_of(path: Path) -> str:
    for kind in sorted(SUBJECT, key=len, reverse=True):
        if kind in path.stem.lower():
            return kind
    raise SystemExit(f"Cannot tell which list {path.name} is; name it like cibrc_mup_<kind>_...")


def clean(cell: str | None) -> str:
    return re.sub(r"\s+", " ", cell or "").strip()


def extract(path: Path, crop: str) -> tuple[list[dict], list[str]]:
    kind = kind_of(path)
    kept: list[dict] = []
    skipped: list[str] = []
    product = ""
    with pdfplumber.open(path) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            for table in page.extract_tables():
                row_crop = ""  # never carry a crop across tables or pages
                for raw in table:
                    cells = [clean(c) for c in raw]
                    filled = [c for c in cells if c]
                    if len(filled) == 1 and cells[0] and PRODUCT_MARKERS.search(cells[0]):
                        product, row_crop = cells[0], ""
                        continue
                    if cells[0]:
                        row_crop = cells[0]
                    if not row_crop.lower().startswith(crop.lower()):
                        continue
                    subject, rest = cells[1], cells[2:]
                    if not subject and rest and re.search(r"[a-z]{3}", rest[0], re.I):
                        # Combination products print the pest/disease one column further right.
                        subject, rest = rest[0], rest[1:]
                    values = [c for c in rest if c]
                    where = f"{path.name} p.{page_no}"
                    if not cells[0] and not kept_same_product(kept, product, where):
                        skipped.append(f"{where} | {product} | crop carried over | {cells}")
                        continue
                    if not product or not subject or len(values) != 4:
                        skipped.append(f"{where} | {product} | irregular columns | {cells}")
                        continue
                    kept.append(
                        {
                            "kind": kind,
                            "product": product,
                            "crop": row_crop,
                            "subject": subject,
                            "ai": values[0],
                            "formulation": values[1],
                            "water": values[2],
                            "waiting": values[3],
                            "where": where,
                        }
                    )
    return kept, skipped


def kept_same_product(kept: list[dict], product: str, where: str) -> bool:
    """A crop-less row continues the previous row only if it is the same product and page."""
    return bool(kept) and kept[-1]["product"] == product and kept[-1]["where"] == where


def render(rows: list[dict], date: str) -> str:
    out = []
    for r in rows:
        subject = SUBJECT[r["kind"]]
        # Seed treatments print instructions where the water volume would be.
        water_label = (
            "How to apply" if len(r["water"]) > 25 else "Dilution in water per hectare (litres)"
        )
        out.append(
            f"## {r['crop']}: CIB&RC approved use of {r['product']} ({r['kind']})\n"
            f"Source: CIB&RC Major Uses of Pesticides as on {date}, {r['where']}\n\n"
            f"Product: {r['product']}\n"
            f"Crop: {r['crop']}\n"
            f"{subject}: {r['subject']}\n"
            f"Dosage per hectare, active ingredient: {r['ai']}\n"
            f"Dosage per hectare, formulation (product): {r['formulation']}\n"
            f"{water_label}: {r['water']}\n"
            f"Waiting period between last application and harvest (days): {r['waiting']}\n"
        )
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdfs", nargs="+", type=Path)
    parser.add_argument("--crop", default=get_settings().crop)
    parser.add_argument("--date", default="30.09.2026", help="'as on' date printed on the lists")
    args = parser.parse_args()

    rows: list[dict] = []
    skipped: list[str] = []
    for pdf in args.pdfs:
        kept, skip = extract(pdf, args.crop)
        rows += kept
        skipped += skip
        print(f"{pdf.name}: kept {len(kept)}, skipped {len(skip)}")

    sources = ROOT / "data" / "sources"
    header = (
        f"# CIB&RC approved uses for {args.crop}\n\n"
        "Rows extracted from the Central Insecticides Board & Registration Committee lists "
        "(Directorate of Plant Protection, Quarantine & Storage). Doses are per hectare as "
        "printed. The lists state they are compiled for guidance, not legal purposes.\n\n"
    )
    out = sources / f"cibrc_approved_uses_{args.crop}.md"
    out.write_text(header + render(rows, args.date), encoding="utf-8")
    # Kept out of data/sources/ itself so it can never be indexed by mistake.
    (sources / "raw").mkdir(exist_ok=True)
    report = sources / "raw" / f"cibrc_skipped_rows_{args.crop}.txt"
    report.write_text("\n".join(skipped) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} rows to {out.name}; {len(skipped)} skipped rows in {report.name}")


if __name__ == "__main__":
    main()
