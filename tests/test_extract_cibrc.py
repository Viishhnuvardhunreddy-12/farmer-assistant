import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
extract_cibrc = importlib.import_module("extract_cibrc_crop")


class FakePage:
    def __init__(self, tables):
        self._tables = tables

    def extract_tables(self):
        return self._tables


class FakePdf:
    def __init__(self, pages):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def run(monkeypatch, pages, name="cibrc_mup_insecticides_test.pdf"):
    monkeypatch.setattr(extract_cibrc.pdfplumber, "open", lambda path: FakePdf(pages))
    return extract_cibrc.extract(Path(name), "chilli")


def test_keeps_clean_rows_with_their_product(monkeypatch):
    table = [
        ["Acephate 95 % SG", None, None, None, None, None, None],
        ["Chilli", "Thrips, Aphid", None, "750", "790", "500", "07"],
        ["Cotton", "Jassids", None, "1", "2", "3", "4"],
    ]
    kept, skipped = run(monkeypatch, [FakePage([table])])
    assert [(r["product"], r["subject"], r["formulation"], r["waiting"]) for r in kept] == [
        ("Acephate 95 % SG", "Thrips, Aphid", "790", "07")
    ]
    assert skipped == []


def test_combination_product_with_shifted_subject(monkeypatch):
    table = [
        ["Pyraclostrobin 10% + Fipronil 5% SC", None, None, None, None, None, None, None],
        ["Chilli", "", "Powdery Mildew", "50+100", "1000", "", "500", "7"],
    ]
    kept, _ = run(monkeypatch, [FakePage([table])], "cibrc_mup_fungicides_test.pdf")
    assert kept[0]["subject"] == "Powdery Mildew" and kept[0]["ai"] == "50+100"
    assert kept[0]["kind"] == "fungicides"


def test_irregular_and_carried_over_rows_are_skipped(monkeypatch):
    page1 = [
        ["Zineb 75%WP", None, None, None, None, None],
        ["Chilli", "Fruit rot", "1.125- 1.5KG", "1.5-2KG", "750-1000 Lt", ""],
    ]
    page2 = [["", "Leafspot", "1", "2", "3", "4"]]  # crop cell empty on a new page
    kept, skipped = run(monkeypatch, [FakePage([page1]), FakePage([page2])])
    assert kept == []
    assert len(skipped) == 1  # the page-2 row has no crop, so it is never matched to chilli
    assert "irregular columns" in skipped[0]
