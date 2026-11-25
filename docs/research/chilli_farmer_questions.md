# What chilli farmers ask: most and least asked questions

Research notes, written 25 Nov 2026. **Not a source for the bot.** This file is never indexed in
ChromaDB and gives no treatment or doses. It tells us which questions the bot must handle, which
documents we still need, and what to put in the test set (`data/eval/questions.jsonl`).

## Where the data comes from

- **Kisan Call Centre (KCC) call logs**, Government of India, published under the Open Government
  Licence – India ([AIKosh listing](https://aikosh.indiaai.gov.in/home/datasets/details/kisan_call_centre_kcc_transcripts_of_farmers_queries_and_answers.html)).
  We read a 1,000,000-row sample mirrored on Hugging Face
  ([Omegaindebt/Kisan_Call_Centre_Transcripts](https://huggingface.co/datasets/Omegaindebt/Kisan_Call_Centre_Transcripts)),
  2010–2023, and kept only the question text, not the answers.
  - 17,598 chilli calls in all India; **3,369 from Andhra Pradesh**, 2,740 from Telangana, 671 from Karnataka.
  - AP districts: Kurnool 1,047, **Guntur 828**, **Prakasam 447**, Anantapur 311, Krishna 229.
    (Palnadu was part of Guntur until 2022.)
- Limits:
  - The question text is the call-centre agent's short English summary ("Farmer asked query on
    …"), not the farmer's own words. There are no Telugu examples.
  - It is a sample, so the percentages show the pattern, not exact numbers.
  - Topics were counted by keyword matching; about 10% of calls didn't fit any topic.
- Other evidence:
  - a survey of 260 Guntur/Prakasam chilli growers: crop protection was their top need, then
    production, then marketing ([FAO AGRIS](https://agris.fao.org/search/en/records/67daddf05d48c9a74a0907a6));
  - [NIPHM KCC FAQs](https://niphm.gov.in/Training/FAQs.pdf);
  - [PPQS black thrips advisory](https://ppqs.gov.in/sites/default/files/adhoc_management_strategies_on_thrips_parvispinus.pdf);
  - press reports on invasive pests and on aflatoxin rejections of Guntur chilli.

## Most asked (AP + Telangana + Karnataka, 6,780 calls)

"Covered?" means whether the bot's current documents answer it: ✅ yes, 🟡 thin, ❌ missing,
❔ not checked yet.

| # | Topic | Share of calls | Example (KCC wording) | In MVP? | Covered? |
|---|---|---|---|---|---|
| 1 | Fertilizer and nutrients (basal, top dressing, boron, micronutrients) | 12.7% | "dosage of boron in chilli" | Yes | ✅ (added 25 Nov) |
| 2 | Weather | 12.1% (**22% in AP**) | "Farmer asked query on weather" | No (Phase 2) | — |
| 3 | "Sucking pests", type not named | 10.5% | "sucking pest management in chilli" | Yes | ✅ |
| 4 | Thrips, incl. black thrips (from 2021) | 7.1% | "black thrips control in chilli" | Yes | ✅ |
| 5 | Leaf curl / virus (upward, downward, gemini virus) | 5.8% | "chilly upward curling management" | Yes | 🟡 |
| 6 | Root rot, stem rot, wilt | 5.4% | "chilli root rot management" | Yes | 🟡 (bacterial wilt ❌) |
| 7 | General plant protection | 4.8% | "plant protection in chilli" | Yes | ✅ |
| 8 | Leaf spot, blight, bacterial leaf spot | 4.4% | "bacterial leaf spot management" | Yes | ❔ |
| 9 | Fruit rot, die-back, anthracnose | 3.5% | "die back and fruit rot management" | Yes | ✅ |
| 10 | Fruit borer, tobacco caterpillar | 3.2% | "chilli fruit borer damage" | Yes | ✅ |
| 11 | Gall midge (mostly AP/TS) | 3.0% | "chilli midge fly management" | Yes | 🟡 (symptoms only) |
| 12 | Market price | 2.6% | "market price of chilli in Guntur" | No (Phase 2) | — |
| 13 | Powdery mildew | 2.6% | "chilli powdery mildew" | Yes | ✅ |
| 14 | Growth, flowering, growth regulators | 2.3% | "plant growth regulator in chillies" | Yes | ✅ (added 25 Nov) |
| 15 | Mites | 2.1% | "mite management in chilli" | Yes | ✅ |
| 16 | Whitefly, aphid, jassid | 2.1% | "white fly & jassids management" | Yes | ❔ |
| 17 | Flower or fruit drop | 1.6% | "flower drop in chilli" | Yes | ✅ (added 25 Nov) |
| 18 | Varieties and seed | 1.5% | "chilli varieties for kharif" | Yes | ✅ (AP varieties added 25 Nov; sowing months ❌) |
| 19 | Weeds | 1.3% | — | Yes | ❔ |
| 20 | Nursery, damping off | 1.2% | — | Yes | ✅ (added 25 Nov) |

What stands out:

- **Sucking pests together** (thrips, mites, whitefly, unnamed sucking pests, and most
  upward-curl calls) are roughly **22% of calls** (estimate). They are the biggest crop problem
  and must work very well.
- **Calls peak September to January**, when the crop is growing and fruiting.
- **Weather is the biggest single topic in AP.** The bot needs a clear, polite reply that it
  doesn't cover weather yet. Today these get the "out of scope" message.
- **Fertilizer questions are the top crop topic** and probably not well covered yet. We need an
  official chilli nutrient schedule (ANGRAU / TNAU / ICAR-IIHR).

## Rarely asked, but real

These are less common, but each needs a sensible answer or a safe fallback.

1. Can I mix a bio-insecticide with a chemical one? Can I mix neem oil with micronutrients? Are
   two named products compatible? *(chemical question: be extra careful)*
2. Can granular MOP go through drip? What fertigation schedule should I use?
3. Leaves dropping because the irrigation water is salty.
4. How many days after laying mulch can I transplant? Is there a mulch subsidy?
5. I sprayed one day before harvest. Is it safe? *(waiting period / residue: chemical question)*
6. Termites or root grubs in chilli.
7. Root-knot nematodes.
8. Rats in the chilli field.
9. Fruits not ripening; how to get better colour and quality.
10. Seedling root treatment before transplanting; seedling age at transplanting.
11. Where can I get Lam farm (ANGRAU) seed or a hybrid's seed?
12. Organic thrips control; home-made antiviral sprays; humic acid for flower set.
13. Can chilli be grown in rabi? What temperature does chilli need?
14. Intercropping with chilli.
15. Subsidy for insect-proof nets or a vermicompost unit.
16. Crop insurance last date and premium.
17. Drying and storage, aflatoxin, export pesticide-residue limits. These are almost absent from
    KCC (under 0.2%) but a real issue in the Guntur trade.
18. "Is this pesticide genuine?" (fake products; seen in the press, not in KCC)
19. Frost protection (North India only; not relevant for Palnadu).

## Outside the MVP (bot should politely say it can't help yet)

- **Weather:** about 22% of AP calls.
- **Mandi prices:** about 3%.
- **Schemes, subsidies, insurance, loans:** under 1%.
- **Where to buy seed or inputs; office phone numbers:** logistics, not crop advice.
- **Export quality and aflatoxin rules:** post-harvest, not in our documents.

## What this means for the app

1. **Find official documents for the gaps**, in this order:
   - fertilizer and nutrient schedule, including boron and fertigation;
   - gall midge;
   - flower/fruit drop and growth regulators;
   - bacterial wilt and bacterial leaf spot;
   - nursery and damping off;
   - AP varieties and sowing months.

   Then re-run the coverage check to fill in the ❔ marks.
2. **Treat mixing, "named product + dose", and "sprayed before harvest" questions as chemical
   questions** in the safety guard, so they always get quotes and safety notes or the expert fallback.
3. **Make the out-of-scope reply useful for weather and prices**, because farmers will ask these a lot.
4. **Build the test set from these topics.** Write 30–50 Telugu questions in farmers' own words,
   weighted like the table above: about a quarter sucking pests, plus fertilizer, leaf curl, wilt,
   fruit rot, gall midge, and several out-of-scope ones. A native speaker should write them and an
   expert should give the right answers.
