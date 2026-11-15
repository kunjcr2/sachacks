# Extraction evaluation

The default `CuratedExtractor` loads five hand-authored, explicitly synthetic protocols. It does not infer rules from prose. All 20 fixture criteria retain exact source quotations; `tests/test_extraction_sources.py` checks every quotation, publication review gates, ambiguity handling, and cache invalidation.

| Check | Result |
| --- | --- |
| Synthetic protocols | 5 |
| Curated criteria | 20 |
| Verbatim source fidelity | 20/20 |
| Curated loading fidelity against the fixture fields | 20/20 |
| LLM precision / recall on unseen protocols | **Not measured** |
| Human corrections to LLM output | **Not measured** |

The loading checks are fixture-integrity checks, **not evidence of automatic extraction accuracy**. The optional OpenAI adapter is covered with a simulated structured response, including public-text-only input, draft-only output and cache behavior. It has not been evaluated with a paid API call. No generated clinical accuracy or recruitment-impact claim is made.

The cached real example is [NCT03548935](https://clinicaltrials.gov/study/NCT03548935), fetched from the official API. It is completed and is shown as source material only; it is never passed off as an active recruiting protocol. The raw API response, exact eligibility text, retrieval timestamp, source URL and text hash are stored in `data/trials/raw/`.

Any automatic extraction needs a separate annotated reference set and qualified semantic review. Verbatim quotations and a valid JSON schema alone cannot establish that an entire protocol has been represented correctly.
