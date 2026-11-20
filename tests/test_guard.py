from app.llm.schemas import Diagnosis, GroundedAnswer, SourceQuote
from app.models import RetrievedChunk
from app.safety.guard import check_answer, check_diagnosis, numbers_in, quote_is_verbatim

CHUNK = RetrievedChunk(
    id="S1",
    text="Spray Tricyclazole 75 WP @ 0.6 g/litre of water at boot leaf stage. "
    "Wear gloves and mask while spraying.",
    source_title="Paddy Guide",
    page=12,
    similarity=0.8,
)


def answer(**overrides) -> GroundedAnswer:
    base = dict(
        answer="Spray Tricyclazole 0.6 g per litre.",
        supported_by_sources=True,
        cited_source_ids=["S1"],
        quotes=[
            SourceQuote(source_id="S1", quote="Tricyclazole 75 WP @ 0.6 g/litre", kind="dosage"),
            SourceQuote(
                source_id="S1", quote="Wear gloves and mask while spraying.", kind="safety"
            ),
        ],
        mentions_chemicals=True,
        confidence="high",
    )
    base.update(overrides)
    return GroundedAnswer(**base)


def test_good_answer_passes():
    result = check_answer(answer(), [CHUNK])
    assert result.ok
    assert len(result.quotes) == 2
    assert not result.add_chemical_safety
    assert not result.add_expert_note


def test_no_sources_falls_back():
    assert check_answer(answer(), []).reason == "no_sources"


def test_low_confidence_falls_back():
    assert check_answer(answer(confidence="low"), [CHUNK]).reason == "low_confidence"


def test_unsupported_falls_back():
    result = check_answer(answer(supported_by_sources=False), [CHUNK])
    assert result.reason == "not_supported_by_sources"


def test_number_not_in_source_falls_back():
    result = check_answer(answer(answer="Spray Tricyclazole 2 g per litre."), [CHUNK])
    assert result.reason == "unverified_number"


def test_numbers_in_other_scripts_are_checked():
    # Telugu digits ౦.౬ == 0.6, which is in the source
    assert check_answer(answer(answer="ట్రైసైక్లాజోల్ ౦.౬ గ్రా"), [CHUNK]).ok
    # Devanagari २ == 2, which is not
    assert check_answer(answer(answer="२ ग्राम"), [CHUNK]).reason == "unverified_number"


def test_paraphrased_dosage_quote_falls_back():
    bad = [SourceQuote(source_id="S1", quote="Tricyclazole 1 g per litre", kind="dosage")]
    assert check_answer(answer(quotes=bad), [CHUNK]).reason == "unverified_quote"


def test_bad_other_quote_is_dropped_not_fatal():
    quotes = [SourceQuote(source_id="S1", quote="something not in the text", kind="other")]
    result = check_answer(answer(quotes=quotes), [CHUNK])
    assert result.ok and result.quotes == []


def test_chemicals_without_safety_quote_adds_safety_note():
    quotes = [SourceQuote(source_id="S1", quote="Tricyclazole 75 WP @ 0.6 g/litre", kind="dosage")]
    assert check_answer(answer(quotes=quotes), [CHUNK]).add_chemical_safety


def test_medium_confidence_adds_expert_note():
    assert check_answer(answer(confidence="medium"), [CHUNK]).add_expert_note


def test_citation_of_unknown_chunk_falls_back():
    assert check_answer(answer(cited_source_ids=["S9"]), [CHUNK]).reason == "no_valid_citations"


def test_quote_matching_ignores_whitespace_and_case():
    assert quote_is_verbatim("tricyclazole  75 wp\n@ 0.6", CHUNK.text)


def test_numbers_in_handles_thousands_separator():
    assert numbers_in("1,000 kg and 2.5 l") == {"1000", "2.5"}


def diag(**overrides) -> Diagnosis:
    base = dict(
        is_plant_photo=True,
        crop_seen="paddy",
        matches_target_crop=True,
        likely_condition="rice blast",
        alternatives=["brown spot"],
        visible_symptoms=["diamond shaped lesions"],
        confidence="high",
    )
    base.update(overrides)
    return Diagnosis(**base)


def test_diagnosis_checks():
    assert check_diagnosis(diag()) == ""
    assert check_diagnosis(diag(is_plant_photo=False)) == "not_plant_photo"
    assert check_diagnosis(diag(matches_target_crop=False)) == "other_crop"
    assert check_diagnosis(diag(confidence="low")) == "unclear_photo"
    assert check_diagnosis(diag(likely_condition="healthy")) == "unclear_photo"
