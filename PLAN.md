> HISTORICAL / SUPERSEDED. This is the pre-pivot plan. CHANGES.md is the product authority; README.md and DEMO.md describe the implemented central architecture. No old workflow is active.

# ReMatch — Build Plan (SacHacks submission)

> **Discover. Reassess. Re-engage. Retain.**
> A privacy-preserving, clinic-controlled clinical-trial matching network whose differentiator is **longitudinal reassessment**: a patient who is ineligible today is not lost forever.

This file is the single source of truth for the coding agent. Read it fully before writing code.

---

## 0. Rules for the agent

1. **Build in phase order (Section 15).** Each phase has a Definition of Done (DoD). Do not start the next phase until the current DoD passes.
2. **Eligibility is decided by deterministic Python code, never by an LLM.** LLMs (if used at all) only _extract_ criteria into the `Criterion` schema, and a human verifies them before distribution.
3. **Identity never leaves the clinic process.** Only the contracts in Section 4.3 may cross the boundary. Any new outbound field requires updating this plan first.
4. **All data is synthetic.** No real PHI anywhere in the repo, ever. Seed with a fixed random seed so the demo is reproducible.
5. **Demo reliability beats feature count.** Cached data, a simulated clock, and one-command reset are mandatory. If something is flaky, cut it (Section 19).
6. **Never claim ReMatch is "the first" of anything.** See Section 20 for approved positioning language.
7. **The system supports screening; it does not determine eligibility.** Every UI surface that shows a match must say so. Investigators make formal eligibility decisions.
8. When a decision is marked **TBD**, build against the interface, use the default, and leave a `# TODO(Kunj):` comment.

---

## 1. Project summary

**Problem.** Clinical-trial recruitment is fragmented. Clinics hold the data but lack continuous matching; sponsors need candidates but can't see identifiable data; patients get screened out once and forgotten, even though labs, medications, conditions, and protocols all change.

**Solution.** A simulated network of three stakeholders around a thin central hub:

| Stakeholder                          | What they see / do in ReMatch                                                                                                                                                  |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Clinic** (trusted identity holder) | Holds identity + FHIR-shaped records. Pulls trial criteria from the hub, matches **locally**, reassesses when data changes, reviews matches, contacts patients.                |
| **Trial Lab / Sponsor**              | Publishes structured eligibility criteria, sees aggregate feasibility across clinics, receives **encrypted, de-identified** candidate packets, confirms or requests more data. |
| **Patient**                          | Sees only what their clinic chooses to surface (clinic-initiated). Controls research preferences, responds to opportunities, can withdraw anytime.                             |
| **Hub** (central platform)           | Trial registry + routing. Sees trial criteria, aggregate counts, and ciphertext. **Never sees identity or readable patient data.**                                             |

**Core demo moment.** Patient `PX-82914`, HbA1c 11.2% → ineligible for a trial requiring 7.5–10%. Three (simulated) months later a new lab shows 9.1%. The clinic's local agent detects the change, re-evaluates, raises a **"previously unmet criterion may now be met"** alert, and a coordinator reviews it. This is the single most important thing to build perfectly.

---

## 2. SacHacks context and judging strategy

Context pulled from the most recent edition found (SacHacks VII, Feb 2026). **The next edition's dates/tracks were not confirmed — verify on sachacks.io / Devpost before final submission.**

- Tracks: Web & App Development; Branding/Design/Marketing; Data & Strategic Analytics (plus partner challenges).
- Prizes seen: Best Overall, Best Social Good/Equity (healthcare explicitly listed), Best Design/UI (Figma link required), Best Solo Hack, honorable mentions.
- Judging: table-to-table, **5-minute presentation + 2-minute Q&A**. Criteria: Innovation & Creativity, Technical Execution, Real-World Impact.
- Submission: Devpost + **GitHub link** (project must be observable, code accessible); video optional. Up to **3 prize tracks** may be selected.
- A judge from IQVIA (clinical research) sat on the prior panel → expect domain questions. Be precise about consent, IRB, and "screening support ≠ eligibility determination."

**Target tracks:** Best Overall · Best Social Good/Equity · Data & Strategic Analytics (or Web & App Dev). Skip Best Design/UI unless time remains (needs a Figma file).

| Criterion           | How ReMatch answers it                                                                                                                                                  |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Innovation          | Federated matching + longitudinal reassessment + cross-trial discovery + data-reuse classification, in one workflow                                                     |
| Technical execution | 5+ independent services, deterministic 3-state engine, unit/recency-aware evaluation, per-trial pseudonyms, end-to-end encryption through the hub, automated leak tests |
| Real-world impact   | Clinical trials fail on recruitment; patients get screened out permanently; privacy blocks data sharing                                                                 |

---

## 3. Decisions

### Locked

| Decision                        | Choice                                                                                                  |
| ------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Matching location               | Federated: inside each clinic first; pseudonymous packet then goes to the trial lab to confirm          |
| Patient data source             | Clinic only (EHR/lab feeds, simulated). No patient uploads                                              |
| Identity mapping                | Clinic only                                                                                             |
| Who initiates research outreach | Clinic only. Patients respond, they don't self-initiate                                                 |
| UI                              | **Streamlit**, three role-specific apps: Patient, Clinic, Trial Lab/Sponsor                             |
| Federation realism              | 2 clinics as separate FastAPI processes with separate DBs (3rd clinic = stretch) + separate hub process |
| Database                        | SQLite, one file per service (replaces PostgreSQL; no cloud/infra). pgvector dropped                    |
| Charts                          | Plotly (replaces Recharts)                                                                              |
| Runtime                         | Local. Optional tunnel (ngrok/cloudflared/VS Code port-forward) for teammates/judges                    |

### TBD (do not block on these)

| Item                                                                                                                               | Default until decided                                                                                 | Owner                                               |
| ---------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| **Eligibility extraction method** (Claude API with structured output vs hand-curated vs local model vs scispaCy/medspaCy-assisted) | Hand-curated JSON via `CuratedExtractor`. LLM path is a stub behind the `CriteriaExtractor` interface | **# TODO(Kunj): pick when building with the agent** |
| Team size / hackathon duration                                                                                                     | Assume 2–4 people, ~24–36 h. P0+P1 phases are the minimum viable demo                                 | Team                                                |
| Next SacHacks edition's tracks/dates                                                                                               | See Section 2                                                                                         | Team                                                |

### Assumptions the agent made (confirm or flip)

1. **Two-tier consent.** _Tier 1 (broad):_ patient agrees to local research matching and to sharing a de-identified packet for confirmation. _Tier 2 (trial-specific):_ after the trial lab confirms, the patient is asked before any contact/identity disclosure. Only Tier-1 patients are evaluated.
2. **A Patient app exists** (added after the "how would it look for the patient side" answer) but stays clinic-initiated: it only shows what the clinic has released.
3. **Pull-based networking.** Clinics poll the hub (outbound-only, matches real hospital firewalls). The hub never calls into a clinic.
4. "Lab" that receives de-identified packets = the **trial lab / sponsor side**, not the diagnostic lab that feeds the clinic.

---

## 4. Architecture

### 4.1 Processes and ports

```
                     ┌─────────────────────────────┐
                     │  HUB  (FastAPI :8000)       │
                     │  trial registry · routing   │
                     │  aggregate signals · audit  │
                     │  sees ciphertext only       │
                     └──────▲───────────▲──────────┘
        pull trials/        │           │   encrypted referrals,
        push aggregates +   │           │   sponsor responses
        encrypted packets   │           │
      ┌─────────────────────┴──┐   ┌────┴─────────────────────┐
      │ CLINIC A (FastAPI :8101)│   │ Streamlit SPONSOR :8502  │
      │ CLINIC B (FastAPI :8102)│   │  (holds private key)     │
      │ [CLINIC C :8103 stretch]│   └──────────────────────────┘
      │  own SQLite each        │
      │  identity + FHIR data   │   ┌──────────────────────────┐
      │  local matching engine  │◄──┤ Streamlit CLINIC  :8501  │
      │  rematch monitor        │   └──────────────────────────┘
      │  pseudonym map          │   ┌──────────────────────────┐
      └────────────▲────────────┘◄──┤ Streamlit PATIENT :8503  │
                   │                └──────────────────────────┘
          simulated lab feed (script/UI button)
```

- Streamlit apps talk to their backend over HTTP using `httpx`. The **sponsor app** talks only to the hub; the **patient app** and **clinic app** talk only to a clinic API; **no UI talks to two clinics' databases directly**.
- Bind backend APIs to `127.0.0.1`. If tunneling for teammates, expose **only** 8501–8503.
- Every backend requires an `X-API-Key` header (value from `.env`) so an accidental port-forward doesn't expose open endpoints.

### 4.2 Package name warning

Do **not** name any package `platform` (collides with Python's stdlib). The central service is `hub/`.

### 4.3 Data boundary contract (what crosses, and when)

| #   | Direction                          | Payload                                                                | Contains                                                                                                                     | Must NOT contain                                                                                |
| --- | ---------------------------------- | ---------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| 1   | Sponsor → Hub → Clinic             | `TrialBundle` (versioned criteria, status)                             | Public trial info, structured criteria with `source_text`                                                                    | Any patient data                                                                                |
| 2   | Clinic → Hub                       | `AggregateSignal`                                                      | Counts per trial/version: evaluated, potential, needs_info, not_matched, new_this_period                                     | Patient identifiers, per-patient rows                                                           |
| 3   | Clinic → Hub → Sponsor             | `CandidatePacket` **sealed-box encrypted to the sponsor's public key** | Per-trial pseudonym, age band, sex, only criterion-relevant evidence, relative timing, reuse classification, rematch history | Name, MRN, DOB, contact info, absolute dates, address/ZIP, free text notes, clinic-internal IDs |
| 4   | Sponsor → Hub → Clinic             | `SponsorResponse`                                                      | `referral_id`, decision (`confirm` / `needs_data` / `decline`), requested criteria IDs, short note                           | Anything attempting to identify a patient                                                       |
| 5   | Clinic → Patient (via patient app) | Opportunity card                                                       | Plain-language trial summary + exactly what would be shared                                                                  | Raw match scores                                                                                |

Rules:

- **Minimum necessary:** the packet includes only fields referenced by the trial's criteria.
- **Gate:** a packet is created only if (a) match status is `POTENTIAL_MATCH`, (b) a coordinator approved it, and (c) patient's Tier-1 consent is `OPTED_IN`.
- The hub stores and relays ciphertext. A "Network Inspector" page proves this live.
- Sponsor never learns identity in the MVP. Identity resolution happens only at the clinic when the pseudonymous ref is mapped back for outreach.

---

## 5. The three views (what each stakeholder sees)

Visual identity per app (set via Streamlit `--theme.*` flags in `run_demo.py`): Clinic = teal with a persistent **🔒 Identity Zone** banner; Sponsor = indigo with a **"De-identified data only"** banner; Patient = warm palette, larger type, plain language.

### 5.1 Clinic app (`ui/clinic_app.py`, :8501) — coordinator

Sidebar: clinic selector (A/B), **demo clock** ("Today: …", **Advance 30 / 90 days** buttons), "Sync trials now", "Reset demo".

Pages:

1. **Overview** — KPIs: patients (Tier-1 opted in), trials received, potential matches, pending reviews, stale-data count. "What left this clinic today" mini-summary.
2. **Review Queue** (hero page) — tasks sorted with `NEW_OPPORTUNITY` (rematch) first. Row → detail panel:
   - Patient header (identity visible here only).
   - Criterion table: criterion · source text · patient value + unit · collected (age in days) · ✅ Met / ❌ Not met / ❓ Unknown · reason (`MISSING`, `STALE`, `UNIT_CONVERTED`) · reuse class chip.
   - **Before → After diff panel** for rematches (e.g. HbA1c 11.2 → 9.1, "previously unmet criterion may now be met").
   - Buttons: **Approve & send de-identified packet**, Hold, Dismiss, notes. Banner: "Screening support only — formal eligibility is determined by the study investigator."
3. **Trials** — trials received from hub, version, status; per-trial local counts; criteria viewer.
4. **Patients** — searchable list with identity; patient detail shows FHIR-shaped Conditions/Observations/Medications, consent status, match history. Forms: **Ingest new lab result** (single observation) and **Simulate lab feed** (loads a prepared bundle).
5. **Data freshness** — the monthly stale-data list: observations past the refresh window, with "recommended re-test" per patient (drives the "update records monthly if stale" idea).
6. **Outreach & participation** — sponsor-confirmed referrals, patient responses, release-to-patient button, reminders, withdrawals.
7. **Privacy log** — every outbound payload (endpoint, keys, size, PII-guard result, pseudonym used) so judges can verify the boundary.

### 5.2 Trial Lab / Sponsor app (`ui/sponsor_app.py`, :8502)

Sidebar: sponsor selector (e.g., "Meridian Research Labs"). Generates/loads an X25519 keypair at start; registers the public key with the hub.

Pages:

1. **Trials** — library of the sponsor's trials. **Publish trial**: pick/paste eligibility text → structured criteria shown side-by-side with source text → mark criteria `verified` → **Publish to network** (bumps version).
2. **Network feasibility** — aggregate-only dashboard: per-trial stacked bars by clinic (potential / needs info / not matched), "new potential this month", funnel (evaluated → potential → approved → confirmed → patient interested → referred).
3. **Candidate inbox** — decrypts packets locally. Card: pseudonym, clinic site, age band, sex, criterion evidence table, reuse-class chips, **rematch badge** ("became eligible after lab change 4 days ago"). Actions: **Confirm**, **Request more data** (choose criteria), **Decline** (reason).
4. **Protocol amendment** _(P2 stretch)_ — edit a criterion (e.g., HbA1c max 10 → 11.5), publish v2 → clinics re-evaluate → new potential matches appear (second rematch trigger).
5. **Network Inspector — "what the hub saw"** — table of every request the hub received: sender, path, size, top-level JSON keys, truncated body (ciphertext shows as base64). Proves no identity reached the middle.

### 5.3 Patient app (`ui/patient_app.py`, :8503)

Demo sign-in: dropdown "Sign in as (demo)" listing patients from the selected clinic. Only talks to the clinic API.

Pages:

1. **My research preferences** — clinic-initiated prompt: "Your clinic would like to know if you're open to being matched with research studies." Options: Yes / Not now / No. Preferred contact method. **Pause or withdraw anytime** button.
2. **Opportunities from my clinic** — shown only after the clinic releases one (post sponsor confirmation). Card: plain-language title, why your clinic thought of you (no scores), what the study involves, **exactly what would be shared** (checklist), buttons **I'm interested / Ask me later / No thanks**.
3. **My participation** — upcoming screening visit, reminders (simulated), "Contact my clinic", **Withdraw** (triggers a retraction message to the sponsor via the clinic; confirms clearly that withdrawing never affects regular care).

Tone: no jargon, reading level ~8th grade, no pressure language. Retention = support, not persuasion.

---

## 6. Domain model and schemas

Use **Pydantic v2** for all shared schemas (`rematch/common/schemas.py`). Use `model_config = ConfigDict(extra="forbid")` on every outbound model.

### 6.1 Field registry (`common/fields.py`)

Canonical keys the matcher understands. Everything else → `unmapped` → `UNKNOWN` with human review.

| key                                                    | kind        | code (verify before finalizing)      | canonical unit  | mutable\* | default recency (days) |
| ------------------------------------------------------ | ----------- | ------------------------------------ | --------------- | --------- | ---------------------- |
| `age`                                                  | demographic | —                                    | years           | no        | —                      |
| `sex`                                                  | demographic | —                                    | —               | no        | —                      |
| `hba1c`                                                | lab         | LOINC 4548-4                         | % (NGSP)        | yes       | 90                     |
| `egfr`                                                 | lab         | LOINC 62238-1                        | mL/min/1.73m²   | yes       | 180                    |
| `creatinine`                                           | lab         | LOINC 2160-0                         | mg/dL           | yes       | 180                    |
| `alt`                                                  | lab         | LOINC 1742-6                         | U/L             | yes       | 180                    |
| `bmi`                                                  | vital       | LOINC 39156-5                        | kg/m²           | yes       | 90                     |
| `sbp` / `dbp`                                          | vital       | LOINC 8480-6 / 8462-4                | mmHg            | yes       | 30                     |
| `cpeptide`                                             | lab         | (placeholder)                        | ng/mL           | yes       | screening-only         |
| `dx_t2dm`                                              | condition   | SNOMED 44054006                      | present/absent  | no        | —                      |
| `dx_ckd`                                               | condition   | SNOMED 709044004                     | present/absent  | no        | —                      |
| `dx_htn`                                               | condition   | SNOMED 38341003                      | present/absent  | no        | —                      |
| `dx_hf`                                                | condition   | SNOMED 84114007                      | present/absent  | no        | —                      |
| `pregnant`                                             | condition   | SNOMED 77386006                      | present/absent  | yes       | 30                     |
| `rx_metformin`, `rx_insulin`, `rx_sglt2i`, `rx_glp1ra` | medication  | internal class map (RxNorm optional) | active/inactive | yes       | —                      |

\*`mutable` = could plausibly change over time. A "watch" is only opened when **all** blocking criteria are mutable. Codes above are best-effort; the demo's visible strings matter more than code accuracy, but verify against LOINC/SNOMED browsers before claiming standards compliance.

### 6.2 `Criterion`

```python
class Criterion(BaseModel):
    id: str                       # e.g. "SYN-0001-I3"
    type: Literal["inclusion", "exclusion"]
    field: str                    # key from the field registry, or "unmapped"
    operator: Literal["between","gte","lte","gt","lt","eq","in","present","absent"]
    min: float | None = None
    max: float | None = None
    value: str | float | list[str] | None = None
    unit: str | None = None
    recency_days: int | None = None            # protocol validity window; None = registry default
    central_lab_required: bool = False         # protocol-specific testing
    assessment_stage: Literal["preliminary","screening_only"] = "preliminary"
    source_text: str                           # verbatim protocol text, always preserved
    extraction: Literal["curated","llm","manual"] = "curated"
    review_status: Literal["draft","verified"] = "draft"   # hub distributes only "verified"
```

Example (from the idea doc):

```json
{
  "id": "SYN-0001-I3",
  "type": "inclusion",
  "field": "hba1c",
  "operator": "between",
  "min": 7.5,
  "max": 10.0,
  "unit": "%",
  "recency_days": 90,
  "source_text": "HbA1c must be between 7.5% and 10%",
  "review_status": "verified"
}
```

### 6.3 `TrialBundle`

`trial_id`, `version:int`, `title`, `plain_language_summary`, `sponsor_id`, `source` (`synthetic` | `clinicaltrials.gov`), `source_ref` (e.g., NCT ID), `status` (`recruiting` | `paused` | `closed`), `last_updated`, `raw_eligibility_text`, `criteria: list[Criterion]`, `visits_summary` (for patient card).

### 6.4 FHIR-shaped clinic records

Store as FHIR R4-shaped JSON in the clinic DB (hand-rolled minimal Pydantic models in `common/fhir.py`; `fhir.resources` is optional). Resources: `Patient` (identity, **clinic-only**), `Condition`, `Observation` (value, unit, `effectiveDateTime`, `method` e.g. `HPLC`/`POC`, `fasting` optional), `MedicationStatement`. Provide `POST /fhir/Observation` and `POST /fhir/Bundle` ingest endpoints so the "lab feed" is a realistic FHIR submission.

### 6.5 `FieldFact` (internal, what the matcher consumes)

`field`, `value`, `unit`, `effective_date`, `method`, `source_resource_id`. Built by `PatientSnapshot.from_fhir(...)`; latest fact per field wins; the snapshot keeps the full history for diffs.

### 6.6 `CriterionResult` / `MatchResult`

```python
CriterionResult: criterion_id, status: MET|NOT_MET|UNKNOWN, reason: OK|MISSING|STALE|UNMAPPED|SCREENING_ONLY,
                 patient_value, patient_unit, normalized_value, effective_date, age_days,
                 reuse_class: REUSABLE|REUSABLE_AFTER_VERIFICATION|REPEAT_REQUIRED|MISSING|N/A,
                 explanation: str
MatchResult:     patient_id, trial_id, trial_version, as_of, status: POTENTIAL_MATCH|NEEDS_INFO|NOT_MATCHED,
                 criteria: list[CriterionResult], blocking_criteria: list[str], watch: bool
```

---

## 7. Matching engine spec (`clinic/matching/engine.py`) — pure functions, no I/O

### 7.1 Semantics

`CriterionResult.status` always means "**does the patient satisfy this requirement**":

- Inclusion: `MET` if the condition is true.
- Exclusion: `MET` if the patient does **not** have the excluded characteristic.
- Missing data → `UNKNOWN` (reason `MISSING`). **Never** auto-fail or auto-pass.
- Data older than the criterion's recency window → `UNKNOWN` (reason `STALE`); keep the last value for display.
- `field == "unmapped"` → `UNKNOWN` (reason `UNMAPPED`).
- `assessment_stage == "screening_only"` → evaluated for display but **excluded from the overall decision**; always listed under "to be assessed at formal screening" (`reuse_class = REPEAT_REQUIRED` if `central_lab_required`).

### 7.2 Overall status

```
if any preliminary criterion is NOT_MET            → NOT_MATCHED
elif any preliminary criterion is UNKNOWN          → NEEDS_INFO
else                                               → POTENTIAL_MATCH
```

`blocking_criteria` = IDs of `NOT_MET` criteria. `watch = True` when status is `NOT_MATCHED` and every blocking criterion's field is `mutable` in the registry (this is what the rematch monitor tracks).

### 7.3 Unit normalization (`common/units.py`)

Convert to canonical unit before comparing; record `UNIT_CONVERTED` in the explanation.

- HbA1c: mmol/mol → % : `% = mmol_mol / 10.929 + 2.15`
- Glucose: mmol/L → mg/dL : `× 18.016`
- Creatinine: µmol/L → mg/dL : `÷ 88.4`
- Unknown/incompatible unit → `UNKNOWN` with reason `UNIT_MISMATCH` (never guess).

### 7.4 Reuse classification (data reusability stage)

For lab/vital criteria that have a value:

- `REUSABLE` — within recency window and (not `central_lab_required`) and method is acceptable.
- `REUSABLE_AFTER_VERIFICATION` — within window but method is point-of-care/unknown, or fasting state required but unknown → coordinator verifies.
- `REPEAT_REQUIRED` — `central_lab_required`, or outside window.
- `MISSING` — no value.
  Show as chips on the coordinator and sponsor views. Goal: communicate "this existing result may avoid a repeat test" without claiming it definitely does.

### 7.5 Engine tests (must exist; see Section 16)

Truth tables for inclusion/exclusion × met/not met/missing/stale; boundary values (HbA1c exactly 7.5 and 10.0 are inclusive); unit conversions; screening-only handling; unmapped criteria.

---

## 8. Longitudinal reassessment spec (`clinic/rematch/`)

### 8.1 Triggers

| Trigger                                              | Source                                                            | Scope of re-evaluation                                                                                                                                                         |
| ---------------------------------------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| T1 New/updated observation, condition, or medication | `POST /fhir/*` ingest                                             | That patient × all recruiting trials whose criteria reference the changed field(s) (inverted index `field → criteria`), **plus** cross-trial discovery against all open trials |
| T2 Time passing (staleness)                          | Monthly refresh job (and demo clock advance)                      | Patients with facts past the refresh window; `POTENTIAL_MATCH` can regress to `NEEDS_INFO` (`STALE`)                                                                           |
| T3 Trial change                                      | Hub trial bundle with higher `version`, new trial, or status flip | All Tier-1 patients × that trial                                                                                                                                               |

### 8.2 Process

1. Compute new `MatchResult`; load previous result for `(patient, trial)`.
2. Persist a `match_history` row (trigger, before, after, diff of criteria that changed).
3. Classify the transition:
   - `NEW_OPPORTUNITY`: `{NOT_MATCHED | NEEDS_INFO | none} → POTENTIAL_MATCH` → create a **coordinator task** (high priority) and flag `rematch=true` if the prior status was `NOT_MATCHED`.
   - `PROGRESS`: `NOT_MATCHED → NEEDS_INFO` → log only.
   - `REGRESSION`: `POTENTIAL_MATCH → NEEDS_INFO/NOT_MATCHED` → log; if a packet was already sent, create an "update sponsor" task.
4. Idempotent: re-running with identical inputs creates no new history rows or tasks (`unique(patient_id, trial_id, trial_version, result_hash)`).

### 8.3 Demo clock (`common/clock.py`)

A process-wide clock with `now()` and `advance(days)`; persisted in the clinic DB so restarts keep state. **All matching, staleness, and "days ago" calculations use this clock, never `datetime.now()`.** Clinic UI exposes the advance buttons.

---

## 9. Privacy, pseudonyms, and encryption (`clinic/deid.py`, `common/crypto.py`)

1. **Per-trial pseudonym:** `ref = "RM-" + base32(HMAC_SHA256(clinic_secret, patient_id || "|" || trial_id))[:10]`. Different per trial (prevents cross-trial linking); stable within a trial (enables longitudinal follow-up). Store `(patient_id, trial_id, ref)` in the clinic `pseudonym_map`. The secret lives only in the clinic's `.env`/keystore.
2. **Display alias:** `PX-xxxxx` is a clinic-local display alias for coordinators; it is **not** the cross-boundary ref.
3. **De-identification (allow-list, not block-list):** the `CandidatePacket` model lists exactly what may exist. Generalizations: age → 5-year band (`90+` for ≥90); absolute dates → **days before packet creation**; no ZIP/address; no free text; only criterion-referenced fields.
4. **`PIIGuard`** runs before every outbound call:
   - schema check (`extra="forbid"`);
   - exact-match scan of the serialized payload against _every_ identity value in the clinic DB (names, MRNs, phones, emails, DOBs, street addresses);
   - regex scan for email, phone, SSN, and ISO dates;
   - on any hit: **block the send**, log `PII_GUARD_BLOCKED`, surface in the Privacy log.
5. **Encryption:** `PyNaCl` `SealedBox` — the clinic encrypts the packet JSON to the sponsor's registered public key; only the sponsor app (private key stored in gitignored `.keys/`) can decrypt. The hub sees `{referral_id, clinic_id, trial_id, key_id, ciphertext_b64, created_at}` only.
6. **Small-cell suppression** for aggregates: `MIN_CELL_SIZE` env var (default `1` for demo because synthetic cohorts are small; document that production would use ≥ 5–10 and show the toggle in the Privacy log page).
7. **Withdrawal:** if consent becomes `WITHDRAWN`, remove the patient from future evaluation, cancel pending tasks, and send a retraction (`referral_id`, reason `withdrawn`) so the sponsor discards the packet.

_Honest framing for judges:_ removing names does not guarantee anonymity — that's why we use per-trial pseudonyms, generalization, minimum-necessary evidence, and encryption. We are **not** claiming HIPAA compliance; HIPAA Safe Harbor / Expert Determination and IRB review would be required for production.

---

## 10. Consent and workflow state machine

### 10.1 Consent (clinic DB)

`broad_status ∈ {NOT_ASKED, OPTED_IN, DECLINED, WITHDRAWN}`, `contact_pref`, `updated_at`, `history[]`.

- Only `OPTED_IN` patients are evaluated, counted in aggregates, or packeted.
- Coordinator can send an "Ask about research" prompt to `NOT_ASKED` patients (clinic-initiated); the patient answers in the Patient app.

### 10.2 Match pipeline (`match.pipeline_state`)

```
NONE ─(POTENTIAL_MATCH)→ PENDING_REVIEW
PENDING_REVIEW ─approve→ SENT_TO_SPONSOR ─┬─sponsor confirm→ SPONSOR_CONFIRMED
                                           ├─needs_data→ SPONSOR_NEEDS_DATA (task to supply/repeat)
                                           └─decline→ SPONSOR_DECLINED
PENDING_REVIEW ─hold→ ON_HOLD       ─dismiss→ DISMISSED
SPONSOR_CONFIRMED ─clinic releases→ PATIENT_OUTREACH ─┬─interested→ PATIENT_INTERESTED → REFERRED_TO_SCREENING
                                                       ├─later→ PATIENT_DEFERRED
                                                       └─no→ PATIENT_DECLINED
(any state) ─withdraw→ WITHDRAWN
```

Eligibility `status` (engine output) and `pipeline_state` (workflow) are separate columns.

---

## 11. API contracts

All JSON, `X-API-Key` required, Pydantic request/response models, OpenAPI enabled.

### 11.1 Hub (`:8000`)

| Method & path                        | Purpose                                                                             |
| ------------------------------------ | ----------------------------------------------------------------------------------- |
| `POST /sponsors/register`            | `{sponsor_id, name, public_key_b64}`                                                |
| `GET /sponsors/{id}/key`             | Clinic fetches the sponsor's public key                                             |
| `POST /trials`                       | Sponsor publishes/updates a `TrialBundle` (rejects if any criterion not `verified`) |
| `GET /trials?since_version=`         | Clinics poll for recruiting trials + bundle versions                                |
| `POST /clinics/register`             | `{clinic_id, name}`                                                                 |
| `POST /signals/aggregate`            | Clinic pushes `AggregateSignal`                                                     |
| `GET /signals/aggregate?trial_id=`   | Sponsor feasibility dashboard                                                       |
| `POST /referrals`                    | Clinic posts sealed packet (`ciphertext_b64`, metadata)                             |
| `GET /sponsors/{id}/referrals`       | Sponsor inbox (ciphertext + metadata)                                               |
| `POST /referrals/{id}/response`      | Sponsor decision                                                                    |
| `GET /clinics/{id}/responses?since=` | Clinic polls for sponsor responses                                                  |
| `POST /referrals/{id}/retract`       | Clinic retraction after withdrawal                                                  |
| `GET /audit`                         | Network Inspector feed (every request the hub saw)                                  |

Hub middleware logs every request: sender, path, size, JSON top-level keys, truncated body.

### 11.2 Clinic (`:8101`, `:8102`) — parameterized by `CLINIC_ID`

| Method & path                                                                                  | Purpose                                                                                       |
| ---------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `GET /patients`, `GET /patients/{id}`                                                          | Identity + summary (UI only)                                                                  |
| `GET /patients/{id}/fhir`                                                                      | Conditions, observations, meds                                                                |
| `POST /fhir/Observation`, `POST /fhir/Bundle`                                                  | Lab feed ingest → triggers T1 rematch                                                         |
| `GET /patients/{id}/consent`, `PUT /patients/{id}/consent`                                     | Tier-1 consent                                                                                |
| `GET /matches?status=&pipeline_state=&trial_id=`                                               | List matches                                                                                  |
| `GET /matches/{id}`                                                                            | Criterion-level detail + history                                                              |
| `POST /matches/{id}/decision`                                                                  | `{action: approve\|hold\|dismiss, note}` — approve builds, guards, encrypts, sends the packet |
| `POST /matches/{id}/release`                                                                   | Release confirmed opportunity to the patient                                                  |
| `POST /matches/{id}/patient-response`                                                          | `{response: interested\|later\|no}`                                                           |
| `POST /patients/{id}/withdraw`                                                                 | Withdraw consent / participation                                                              |
| `GET /tasks`                                                                                   | Coordinator queue                                                                             |
| `GET /freshness`                                                                               | Stale-data list                                                                               |
| `GET /privacy-log`                                                                             | Outbound payload log                                                                          |
| `POST /admin/sync`, `POST /admin/clock/advance`, `POST /admin/reset`, `POST /admin/reevaluate` | Demo controls                                                                                 |

Background task (FastAPI lifespan): every `SYNC_INTERVAL_SECONDS` (default 5) pull trials and sponsor responses; every simulated 30 days run the staleness sweep (T2).

---

## 12. Data

### 12.1 Synthetic patients (`scripts/generate_synthetic.py --seed 42`)

- Clinic A "Sunrise Family Health" ≈ 40 patients; Clinic B "Delta Valley Endocrinology" ≈ 30; fictional org names only; names via `Faker` with fixed seed.
- Mix: T2DM ~60%, CKD stage 3 subset, hypertension ~40%, obesity subset, varied meds; consent mix ≈ 80% OPTED_IN, 10% NOT_ASKED, 10% DECLINED.
- Each patient: 2–6 observations over the prior 12 months with realistic values and mixed methods (HPLC / POC).
- **Scripted storyline patients** (fixed IDs, do not randomize):
  | Alias | Clinic | Story |
  |---|---|---|
  | `PX-82914` | A | **Hero.** 58, T2DM, HbA1c 11.2% (14 days before t0), eGFR 71, on metformin, no insulin. Blocked only by HbA1c → `NOT_MATCHED`, `watch=true`. At t0+90d lab feed delivers HbA1c 9.1% and eGFR 68 → `POTENTIAL_MATCH` |
  | `PX-10442` | A | Already `POTENTIAL_MATCH` at t0 (shows baseline path) |
  | `PX-33071` | A | eGFR 7 months old → `NEEDS_INFO` (`STALE`), appears in Data freshness |
  | `PX-55820` | B | Matches at t0 → Clinic B's aggregate differs from A's |
  | `PX-91003` | A | `DECLINED` research → never evaluated, never counted |
  | `PX-47716` | A | On insulin (exclusion) → permanently `NOT_MATCHED`, `watch=false` |

### 12.2 Trials (`data/trials/`)

- **Hero trial `SYN-0001` "ReNew-T2D-01"** (clearly synthetic): inclusion — age 40–70, T2DM, **HbA1c 7.5–10.0%** (90d), eGFR ≥ 45 (180d), BMI 25–40, on metformin; exclusion — insulin use, pregnancy; screening-only — C-peptide (central lab). Cached under `structured/`.
- 4 more synthetic trials covering diabetes, CKD, hypertension, and obesity for cross-trial discovery (e.g., `SYN-0002` CKD with eGFR 30–60; `SYN-0003` hypertension with SBP 140–180).
- **ClinicalTrials.gov discovery (`extraction/ctgov.py`):** call the v2 API (`https://clinicaltrials.gov/api/v2/studies`), filter to recruiting studies by condition, and **cache raw JSON** to `data/trials/raw/` so the demo works offline. Use `protocolSection.eligibilityModule` (`eligibilityCriteria`, `minimumAge`, `maximumAge`, `sex`) plus status/update dates. Preserve original eligibility text, NCT ID, source, status, and last-update date. Real trials without verified criteria are shown in the Sponsor "Trials" page as **draft/not distributed**. Verify the exact response field names against a live response when building.

---

## 13. Eligibility extraction — **TBD (# TODO(Kunj))**

Build to the interface; choose the implementation during the agent session.

```python
class CriteriaExtractor(Protocol):
    def extract(self, trial_id: str, eligibility_text: str) -> list[Criterion]: ...
```

- **`CuratedExtractor` (default, required):** loads `data/trials/structured/<trial_id>.json`. This keeps the demo deterministic.
- **`LLMExtractor` (stub):** `# TODO(Kunj): choose model/provider.` Requirements regardless of choice:
  - output validates against `Criterion` (structured output / JSON schema), temperature 0;
  - preserve `source_text` verbatim; map to registry fields; emit `field="unmapped"` instead of guessing;
  - cache by `sha256(eligibility_text + model_id)` in `data/trials/cache/`;
  - set `extraction="llm"`, `review_status="draft"`; **a human must mark `verified` in the Sponsor app** before the hub accepts it;
  - evaluate against a golden set (the 5 curated trials): report per-field precision/recall in a short `docs/extraction_eval.md`.
- Options to compare: hosted LLM with structured outputs · local open model · scispaCy/medspaCy for entity assistance + rules. Note that the choice does **not** affect the matcher or any other phase.

---

## 14. Repo structure, stack, and running

```
rematch/
├── plan.md
├── README.md                  # judge-facing: 60-second pitch, screenshots, run steps
├── pyproject.toml             # or requirements.txt
├── Makefile                   # setup · seed · demo · reset · test
├── .env.example               # API keys, clinic secrets, ports, SYNC_INTERVAL_SECONDS, MIN_CELL_SIZE
├── data/
│   ├── trials/{raw,structured,cache}/
│   └── synthetic/             # generated, gitignored except fixed storyline fixtures
├── rematch/
│   ├── common/    schemas.py fhir.py fields.py units.py clock.py crypto.py config.py
│   ├── extraction/ base.py curated.py llm.py(stub) ctgov.py
│   ├── hub/       main.py db.py routers/ audit.py
│   ├── clinic/    main.py db.py ingest.py deid.py outreach.py seed.py
│   │   ├── matching/ engine.py evaluators.py snapshot.py
│   │   └── rematch/  monitor.py events.py
│   └── ui/        clinic_app.py sponsor_app.py patient_app.py api_client.py components.py
├── scripts/       fetch_trials.py generate_synthetic.py run_demo.py reset_demo.py simulate_lab_feed.py
├── .keys/                     # gitignored sponsor keypairs
└── tests/
```

| Layer          | Tech                                                                      |
| -------------- | ------------------------------------------------------------------------- |
| Services       | Python 3.11+, FastAPI, Uvicorn, `httpx`                                   |
| Models         | Pydantic v2                                                               |
| Storage        | SQLite via SQLModel (or SQLAlchemy 2.0) — one DB file per service         |
| UI             | Streamlit (`st.fragment(run_every="5s")` for live panels), Plotly, pandas |
| Crypto         | PyNaCl                                                                    |
| Synthetic data | Faker (seeded)                                                            |
| Tests          | pytest + FastAPI `TestClient`                                             |
| Optional       | scispaCy / medspaCy (extraction assist), LLM SDK (TBD)                    |

**Run:**

```
make setup      # venv + deps
make seed       # generate synthetic patients + load trials + keys
make demo       # scripts/run_demo.py: starts hub, clinic A, clinic B, 3 Streamlit apps; prints URLs
make reset      # restore the exact t0 demo state in seconds
make test
```

`run_demo.py` starts all processes with `subprocess`, waits for health checks, passes per-app Streamlit theme flags, and shuts everything down on Ctrl-C.

**Collab / port-forwarding:** run locally on one machine; share via VS Code port forwarding, `cloudflared`, or `ngrok` on **8501–8503 only**. Colab is possible but running 6 processes there is clumsy — treat it as a fallback. Keep `.env` secrets out of git.

---

## 15. Implementation phases

Effort: S ≈ 1–2 h, M ≈ 3–5 h, L ≈ 6+ h. **P0–P4 plus a minimal P5 is the minimum demo.**

### Phase 0 — Foundations (S)

- [ ] Repo scaffold, `config.py` (ports, keys, env), `clock.py`, `fields.py`, `units.py`, `schemas.py`, `fhir.py`.
- [ ] `Makefile`, `.env.example`, `run_demo.py` skeleton with health checks.
- **DoD:** `make test` runs; unit-conversion tests pass; clock advance/persist works.

### Phase 1 — Matching engine (M) ★

- [ ] `snapshot.py` (FHIR → `FieldFact`), `evaluators.py` (operators, recency, units), `engine.py` (3-state, screening-only, blocking/watch, reuse classes).
- [ ] Curated hero trial + 4 synthetic trials in `structured/`.
- **DoD:** truth-table tests and the hero scenario unit test pass (11.2 → `NOT_MATCHED` with `blocking=[HbA1c]`, `watch=true`; 9.1 → `POTENTIAL_MATCH`; exactly-10.0 inclusive; stale → `NEEDS_INFO`).

### Phase 2 — Clinic service (L)

- [ ] DB models (identity, clinical, consent, trial cache, match, history, task, pseudonym map, privacy log), seed script with storyline patients.
- [ ] Ingest endpoints, evaluation on trial sync, T1/T2/T3 rematch with idempotency, transition classification, tasks.
- [ ] Clinic API per Section 11.2.
- **DoD:** pytest integration test runs the hero story against Clinic A via `TestClient`: sync trial → hero `NOT_MATCHED` → advance 90d → ingest bundle → `NEW_OPPORTUNITY` task exists with a before/after diff; declined patient never evaluated.

### Phase 3 — Hub (M)

- [ ] Trial registry (verified-only), versioning, aggregate signals, referral relay, responses, audit middleware, API-key auth.
- **DoD:** two clinics pull trials, push aggregates; `/audit` shows requests with keys/sizes; hub tests pass with no patient fields in any stored payload.

### Phase 4 — Privacy and referral flow (M) ★

- [ ] `deid.py`: pseudonyms, age bands, relative dates, allow-list `CandidatePacket`, `PIIGuard`.
- [ ] `crypto.py`: sealed-box encrypt/decrypt; sponsor keypair generation/registration.
- [ ] Approve → guard → encrypt → hub → sponsor decrypts → response → clinic polls → pipeline states advance → release → patient response → referred.
- **DoD:** leak test passes (seeded identity strings never appear in any hub-stored or hub-logged payload); consent-gating test passes; full pipeline test passes end to end.

### Phase 5 — Streamlit apps (L)

- [ ] `api_client.py`, shared components (status chips, criterion table, diff panel, banners).
- [ ] **Clinic app:** Overview, Review Queue (with diff panel), Patients (ingest + simulate feed), Data freshness, Outreach, Privacy log, clock controls.
- [ ] **Sponsor app:** Trials/publish, Network feasibility (Plotly), Candidate inbox (decrypt + actions), Network Inspector.
- [ ] **Patient app:** Preferences, Opportunities, Participation/withdraw.
- **DoD:** a person who has never seen the project can run the Section 17 script from the UI alone, in under 5 minutes, with no terminal commands after `make demo`.

### Phase 6 — Polish, docs, submission (M)

- [ ] `make reset` restores t0 reliably; run the full demo 3× clean.
- [ ] README with architecture diagram, "what crosses the boundary" table, screenshots, honest limitations, competitor positioning.
- [ ] Record a 2–3 min backup demo video; prepare the Devpost entry (Section 18).
- **DoD:** fresh clone → `make setup seed demo` works; backup video exists.

### Phase 7 — Stretch (pick in this order)

1. **Protocol amendment trigger (T3)** in the Sponsor app (HbA1c max 10 → 11.5 creates new matches).
2. Clinic C (third process; zero code changes expected, config only).
3. ClinicalTrials.gov live-fetch UI with raw-vs-structured side-by-side.
4. LLM extractor implementation (Section 13).
5. Reminders/"Retain" extras (simulated SMS-style reminders in the patient app).
6. Small-cell suppression toggle with live effect on the feasibility chart.
7. medspaCy-assisted extraction for free-text conditions.

---

## 16. Testing plan (`tests/`)

| Test                          | Asserts                                                                                  |
| ----------------------------- | ---------------------------------------------------------------------------------------- |
| `test_engine_truth_tables`    | Inclusion/exclusion × met/not met/missing/stale/unmapped/unit-mismatch                   |
| `test_boundaries`             | HbA1c 7.5 and 10.0 inclusive; 10.01 → not met                                            |
| `test_units`                  | mmol/mol ↔ %, µmol/L ↔ mg/dL, glucose conversions                                        |
| `test_screening_only`         | C-peptide unknown doesn't block `POTENTIAL_MATCH` and is listed for screening            |
| `test_rematch_hero`           | Full 11.2 → 9.1 story with before/after diff and exactly one task                        |
| `test_rematch_idempotent`     | Re-running changes nothing                                                               |
| `test_staleness_regression`   | `POTENTIAL_MATCH` → `NEEDS_INFO` after clock advance                                     |
| `test_consent_gating`         | DECLINED/WITHDRAWN/NOT_ASKED never evaluated, counted, or packeted                       |
| `test_pii_guard`              | Injecting a real identity string into a packet blocks the send                           |
| `test_no_identity_at_hub`     | After the full flow, scan hub DB + audit log for every seeded identity value → zero hits |
| `test_pseudonyms`             | Same patient → same ref within a trial, different across trials                          |
| `test_encryption_roundtrip`   | Only the sponsor key decrypts; hub-stored blob is opaque                                 |
| `test_pipeline_states`        | Legal transitions only; withdrawal retracts the referral                                 |
| `test_hub_rejects_unverified` | Draft criteria cannot be published                                                       |

---

## 17. Demo script (5 minutes) and storyline

Setup before judges arrive: `make reset`; three browser windows side by side (Clinic :8501, Sponsor :8502, Patient :8503) plus the Network Inspector tab ready.

| Time | Screen                 | Beat                                                                                                                                                                           |
| ---- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 0:00 | Slide/voice            | One-line problem: "You're screened out once and never looked at again."                                                                                                        |
| 0:20 | **Sponsor**            | Publish `ReNew-T2D-01`: source text next to structured criteria (HbA1c 7.5–10), mark verified, publish                                                                         |
| 0:50 | **Clinic A**           | Trial arrives. Local match runs. `PX-82914` = ❌ HbA1c 11.2 — "watching". Overview shows only counts leaving                                                                   |
| 1:15 | **Sponsor**            | Feasibility chart: Clinic A vs Clinic B aggregates, no rows, no names                                                                                                          |
| 1:35 | **Network Inspector**  | "This is everything the hub has seen." No identity. Ciphertext only                                                                                                            |
| 1:55 | **Clinic A**           | Click **Advance 90 days**, then **Simulate lab feed** → new HbA1c 9.1%                                                                                                         |
| 2:15 | **Clinic A**           | Rematch alert fires: before/after diff, "previously unmet criterion may now be met", other trials also checked                                                                 |
| 2:45 | **Clinic A**           | Coordinator opens the case: criterion table, reuse chips (HbA1c _reusable after verification_, C-peptide _repeat at screening_). Click **Approve & send de-identified packet** |
| 3:15 | **Sponsor**            | Inbox: pseudonym `RM-…`, age band 55–59, evidence, rematch badge. **Confirm**                                                                                                  |
| 3:40 | **Clinic A → Patient** | Clinic releases; Patient app shows plain-language card with "what will be shared". Patient clicks **I'm interested**                                                           |
| 4:10 | **Clinic A**           | Status → referred to screening. Privacy log shows each outbound payload and PII-guard pass                                                                                     |
| 4:30 | Voice                  | Withdraw is one click; differentiator (longitudinal reassessment + clinic control); honest note on competitors and what's next                                                 |

Fallback if live fails: play the backup video; `make reset` takes seconds.

---

## 18. Devpost / submission checklist

- [ ] Verify the current SacHacks dates, tracks, judging criteria, and submission deadline.
- [ ] Select up to 3 prize tracks intentionally (Best Overall, Social Good/Equity, Data/Analytics or Web & App Dev).
- [ ] Public GitHub repo with a README judges can run; the project must be observable.
- [ ] Description clearly states: problem, solution, why it matters, tracks selected.
- [ ] Screenshots: Review Queue diff panel, Network Inspector, Patient card.
- [ ] Backup demo video (2–3 min) linked.
- [ ] "Synthetic data only / not a medical device / screening support" disclaimer.
- [ ] Prepare Q&A answers (Section 20).

---

## 19. Risks and cut list

| Risk                                 | Mitigation / cut                                                                                                                                 |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Too many processes to start reliably | `run_demo.py` with health checks; fallback: single-process mode that mounts clinic routers in one app (flag `SINGLE_PROCESS=1`)                  |
| Streamlit state/refresh glitches     | Keep state in the backends; UI is stateless besides selection; use `st.fragment` for polling; manual refresh buttons as fallback                 |
| Extraction (TBD) slips               | Default `CuratedExtractor` already covers the demo                                                                                               |
| Crypto/key handling bugs             | Cut to hub-stored plaintext **de-identified** packets only as a last resort, and say so honestly in the submission                               |
| Patient app time sink                | Reduce to a single Opportunities page + withdraw                                                                                                 |
| Time                                 | **Cut order:** Phase 7 → Data freshness page → Patient reminders → Sponsor feasibility charts → Clinic B (keep one clinic + scripted aggregates) |

---

## 20. Positioning, competitors, and Q&A prep

**Do not claim** ReMatch is first to do federated or privacy-preserving trial matching. Existing players include Oncoshot (federated hospital matching), TriNetX (institution/sponsor network), Citeline PatientMatch, GenMD, and Emtrial.

**Approved positioning:** "ReMatch explores the combination of (1) patient-controlled research engagement, (2) clinic-controlled federated matching, (3) **longitudinal reassessment**, (4) cross-trial discovery, and (5) reuse of existing assessments. Commercial differentiation still needs customer validation."

Likely questions:

- _"Does the AI decide eligibility?"_ No. Deterministic rules; a coordinator reviews; the investigator decides formally.
- _"Is this HIPAA compliant?"_ Prototype with synthetic data. Production needs HIPAA analysis (de-identification method), IRB review, BAAs/data agreements.
- _"Why not just remove names?"_ Quasi-identifiers; hence per-trial pseudonyms, age bands, relative dates, minimum-necessary fields, encryption.
- _"What if data is missing or old?"_ `UNKNOWN`, never auto-pass/fail; staleness handled explicitly.
- _"Do patients get pressured to stay?"_ No. Clinic-initiated only, consent tiers, one-click withdrawal.
- _"How would this integrate with real EHRs?"_ FHIR R4 interfaces (`Observation`, `Condition`, `MedicationStatement`); clinics vary, so integration is the hardest real-world step.

---

## 21. Open items checklist

- [ ] **Extraction method** — # TODO(Kunj)
- [ ] Confirm two-tier consent vs. consent-before-any-packet (Section 3 assumption 1)
- [ ] Confirm hackathon dates, duration, and tracks for the next SacHacks
- [ ] Team size and role split (suggested: engine/clinic · hub/crypto · Streamlit UIs · data/demo/README)
- [ ] Verify LOINC/SNOMED codes before citing standards compliance
- [ ] Decide whether to target Best Design/UI (needs a Figma link)
- [ ] Decide on a 3rd clinic (config-only stretch)

---

# ADDENDUM — Missing Implementation Decisions and HackRx 2026 Clarifications

> **Preservation note:** Sections 0–21 above are reproduced **verbatim** from the uploaded ReMatch build plan. This addendum only supplies implementation decisions and details that were absent or left TBD. It does not delete or rewrite existing project requirements. Where the original describes a TBD or an older event, the explicit clarifications below apply to this HackRx build.
>
> **Architecture remains unchanged:** Each clinic holds the patient identity and medical record, performs screening locally, and sends only allowed, encrypted candidate evidence to the sponsor through the hub. This is **not** a proposal to upload everyone's plaintext medical data to a shared central database.

## 22. Gap audit — what is already present versus genuinely missing

| Topic discussed                                                                                                 | Already present in original                             | Addition needed                                                                                                                              |
| --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| ClinicalTrials.gov eligibility criteria and LLM-to-JSON parsing                                                 | Sections 1, 4, 6, 12.2, 13                              | Decide **where extraction runs**, which API response fields to use, exact validation/publishing sequence, and operational fallback.          |
| Deterministic `MET` / `NOT_MET` / `UNKNOWN` decision engine                                                     | Sections 6–7, 15–16                                     | No architectural change. Add extraction-to-engine integration acceptance checks.                                                             |
| Patient identity separated from medical facts                                                                   | Sections 3–4, 9                                         | **Encrypt names, contact information and identifiers in the clinic database at rest**, rather than only encrypting outbound sponsor packets. |
| Per-trial pseudonyms, minimum-necessary candidate packets, and public-key encryption in transit through the hub | Sections 4.3 and 9                                      | Keep exactly as specified. Clarify it is a **separate encryption layer** from local identity encryption.                                     |
| Change-triggered eligibility reevaluation, stale results, protocol amendments                                   | Sections 5, 7–8, 11, 15–17                              | No new algorithm needed. Add rules for situations where the clinic **never receives** an updated record.                                     |
| Free, realistic, changing medical records for a demo                                                            | Section 12 uses Faker and simulated FHIR                | Optional **Synthea FHIR R4** import and public FHIR sandbox path; keep seeded storyline fixtures as the guaranteed fallback.                 |
| One-day hackathon and prize categories                                                                          | Sections 2–3, 18, 21 refer to an older SacHacks edition | Add **verified HackRx 2026** event facts without altering the historic text above.                                                           |

## 23. Eligibility extraction — resolved source, execution location, and workflow

### 23.1 Exactly where the eligibility text comes from

- **Primary source:** Official, free [ClinicalTrials.gov API v2](https://clinicaltrials.gov/data-api/api). Obtain trials using `GET https://clinicaltrials.gov/api/v2/studies` with a condition query and recruitment-status filter. Select a small, inspected subset rather than ingesting every result.
- **For each trial:** Fetch its detailed record using `GET https://clinicaltrials.gov/api/v2/studies/{NCT_ID}`. Read `protocolSection.eligibilityModule.eligibilityCriteria` for the narrative criteria and `minimumAge`, `maximumAge`, `sex` for additional structured information when provided; also retain status, update metadata and `nctId`. Validate actual field paths against a fetched response, as already required in Section 12.2.
- **Trial-specific provenance:** Store `NCT_ID`, original eligibility text, retrieval timestamp, trial version/hash, exact source snippets, and extraction status. Never invent unsupported criteria to fill empty fields.
- **Default demo:** The existing five synthetic, manually verified trial JSON fixtures remain authoritative and sufficient when the live API, parser, or provider is unavailable.

### 23.2 Where the extraction code executes

**Run the extraction at the trial/sponsor ingestion boundary, before publishing a `TrialBundle` to the hub, or as an offline pre-demo script.** It is a data-preparation step, not part of live patient matching.

```text
Public ClinicalTrials.gov trial record
     -> extraction/ctgov.py fetch and local raw-cache
     -> extraction/llm.py (hosted structured extraction, optional)
        OR extraction/curated.py (required deterministic fallback)
     -> schema + provenance + source-text checks
     -> sponsor human reviews and marks each criterion VERIFIED
     -> verified TrialBundle published to the hub
     -> clinics pull bundle and match LOCAL medical facts using Python
```

**Do not send patient records, names, medical facts, or clinic identifiers to the LLM extraction provider.** The extractor receives **public trial criteria only**. Sponsor publication still requires human verification under the already-defined rules.

### 23.3 Extraction provider decision for this prototype

- **Preferred optional automation:** An OpenAI API model that supports **Structured Outputs** to generate JSON validated against a Pydantic representation of the existing `Criterion` contract. Configure `OPENAI_API_KEY`, `OPENAI_MODEL`, and `EXTRACTION_MODE=llm` through `.env` (do not commit keys). This API may have usage costs; the project does **not** depend on a free model endpoint.
- **Required default:** `EXTRACTION_MODE=curated` invokes `CuratedExtractor` and reads `data/trials/structured/<trial_id>.json`, preserving the original Section 13 decision and keeping the demo completely offline.
- The two implementations share the existing `CriteriaExtractor` interface. The chosen LLM/model is swappable; no patient-side or matching code may depend on it.
- If use of an external LLM is undesirable, keep the curated path and demonstrate the manual-review step. A local model is a stretch feature, not a dependency.

### 23.4 Extraction contract and validation

An extracted record must satisfy **all** of the following before it can be marked verified:

1. `field` is a canonical key in `common/fields.py`, or explicitly `unmapped`. Unsupported concepts are **never silently guessed**.
2. `type`, `operator`, units, numerical bounds, and inclusion/exclusion polarity are semantically correct; `min <= max` when both exist.
3. `source_text` is a **verbatim substring of the fetched trial eligibility text** (or the explicitly identified structured source field for age/sex), with its exact source location saved internally. Reject fabricated citations.
4. The parser detects multi-clause expressions such as `AND`, `OR`, nested exceptions, prior-treatment windows, and diagnosis-specific conditions. If the current flat `Criterion` schema cannot represent a clause **without changing its logic**, emit an `unmapped`/manual-review criterion rather than publishing a misleading rule. Do not add a new matcher operator as a shortcut.
5. Every output is initially `review_status="draft"`; a human verifies against the original wording in the Sponsor UI. Unverified drafts are not distributed.
6. Cache the parsed output using a hash of the exact public text and model ID. Changes in the protocol invalidate that cache entry. Run extraction again, require review again, then increment `TrialBundle.version`.
7. Log extraction failures visibly; fall back to curated criteria without substituting a hallucinated result.

**Recommended prompt contract (for `LLMExtractor`):**

```text
You extract explicit eligibility criteria from PUBLIC clinical-trial text.
Return only instances of the supplied Criterion schema.
Never decide whether a patient is eligible. Never infer absent requirements.
Copy each source_text verbatim. Preserve inclusion/exclusion polarity,
operators, thresholds and units. If a requirement is ambiguous or cannot
be represented safely by the schema, mark it unmapped for human review.
Patient records are not included in this task.
```

**Demo-quality measurement:** For 5 manually curated trials, calculate criterion/field precision and recall, and report the number of `unmapped` or reviewer-corrected criteria. This evaluates extraction separately from matching accuracy. An extraction error must never be hidden by the deterministic engine.

### 23.5 Additional files to implement (no original files removed)

- `rematch/extraction/llm.py` — real optional structured-output adapter rather than a stub.
- `rematch/extraction/validate.py` — `Criterion` and source-quotation validation.
- `scripts/extract_trials.py` — fetch/cache/extract/verify-draft batch helper.
- `tests/test_extraction_sources.py` — source fidelity, logical ambiguity, cache invalidation, and publication gate.
- `docs/extraction_eval.md` — reviewed trial sample, error table and honest metrics.

## 24. Identity encryption at rest — the other missing layer

### 24.1 What is encrypted and what stays matchable

The original specification already encrypts **candidate packets in transit through the hub** via PyNaCl sealed boxes for the sponsor. **Keep that unchanged.** Add a **separate, clinic-local identity vault**:

| Data                                                                         | Storage / access                                                         | Encryption for the demo                                                                                                                                |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Name, email, phone, date of birth, MRN, address and other direct identifiers | Clinic-local `patient_identity_vault`, joined by opaque local patient ID | **AES-256-GCM authenticated encryption at rest.** Never in hub/sponsor data.                                                                           |
| Diagnoses, conditions, HbA1c, eGFR, medications, timestamped observations    | Clinic-local clinical tables, keyed by opaque clinic patient ID          | Available to **authorized local matcher** in memory; no plaintext medical record is sent to the hub. Protect full DB/backups and access in production. |
| `(patient_id, trial_id) -> per-trial pseudonym`                              | Clinic-local `pseudonym_map`                                             | Local mapping protected with clinic access controls; no global identity map.                                                                           |
| Minimum-necessary, allowed candidate evidence                                | Clinic creates it only after consent and coordinator review              | **Existing PyNaCl `SealedBox(sponsor_public_key)`** before the hub receives it.                                                                        |
| Hub trial registry and aggregate counts                                      | Central hub                                                              | Public criteria and suppression-controlled aggregates only; no clinical row-level records.                                                             |

**Why two algorithms:** AES-GCM is appropriate for encrypting locally stored identity values that the clinic can later decrypt using its own symmetric key; PyNaCl sealed boxes let a clinic encrypt sponsor-bound packets with the **sponsor's public key** so only that sponsor's private key can open them. They address different trust boundaries.

**Privacy claim to make:** The matching engine works on **pseudonymized clinic-local clinical facts without seeing patient names**; identity is decrypted only inside an **authorized clinic workflow**, normally when a coordinator needs to review or contact someone. This does **not** guarantee anonymity: medical attributes may still be identifying, and simply removing names is not HIPAA de-identification.

### 24.2 Clinic identity-vault storage and keys

Add `patient_identity_vault` to **each clinic's existing SQLite database**:

```text
clinic_local_patient_id   TEXT PRIMARY KEY  -- opaque, not MRN/name
key_id                    TEXT              -- key version, e.g. clinic-a-v1
nonce_b64                 TEXT              -- fresh random 96-bit AES-GCM nonce
ciphertext_b64            TEXT              -- encrypted JSON + GCM auth tag
created_at, updated_at    TEXT
```

- Serialize a clinic-only `IdentityRecord` containing name, MRN, DOB, contact details and address to JSON. **Do not duplicate these plaintext fields in ordinary patient tables, snapshots, logs, or outbound schemas.**
- Generate one **independent 256-bit random key per clinic**, stored via an environment variable or ignored local keystore for the demo. Key material is **never stored in SQLite, the hub, source control, or screenshots**.
- Generate a **fresh random 12-byte nonce every time** an identity record is encrypted. Do not reuse nonce/key pairs.
- Bind the ciphertext to `clinic_id`, opaque `patient_id`, and schema/version using AES-GCM **associated authenticated data (AAD)**; mismatched record IDs or clinics must fail decryption.
- `key_id` supports future key rotation; the prototype does not need an automatic rotation service.
- Keep clinic keys and sponsor private keys separate; they are not interchangeable and neither belongs in a browser or a hub database.
- Add `cryptography` as the dependency for the **clinic identity vault**, leaving the source plan's `PyNaCl` dependency in place.

**Minimal implementation (inside `rematch/clinic/identity_vault.py`):**

```python
import base64
import json
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _aad(clinic_id: str, patient_id: str) -> bytes:
    return json.dumps(["identity-v1", clinic_id, patient_id],
                      separators=(",", ":")).encode("utf-8")


def encrypt_identity(identity: dict, clinic_id: str, patient_id: str,
                     key: bytes) -> dict:
    assert len(key) == 32, "AES-256-GCM requires a 32-byte key"
    nonce = os.urandom(12)
    payload = json.dumps(identity, sort_keys=True).encode("utf-8")
    encrypted = AESGCM(key).encrypt(nonce, payload, _aad(clinic_id, patient_id))
    return {
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "ciphertext_b64": base64.b64encode(encrypted).decode("ascii"),
    }


def decrypt_identity(row: dict, clinic_id: str, patient_id: str,
                     key: bytes) -> dict:
    nonce = base64.b64decode(row["nonce_b64"])
    encrypted = base64.b64decode(row["ciphertext_b64"])
    data = AESGCM(key).decrypt(nonce, encrypted, _aad(clinic_id, patient_id))
    return json.loads(data)
```

To generate a demo key once per clinic (save securely to `.env` / ignored keystore, **do not print in normal logs**): `AESGCM.generate_key(bit_length=256)`. Encode the key as base64 when storing in the env file and decode it on service startup. Use service-owned secrets, not a single shared key for all clinics.

### 24.3 Decryption workflow and access control

```text
Trial criteria -> clinic-local matching on clinical attributes
             -> potential match (no identity needed)
             -> authorized coordinator opens review
             -> clinic decrypts that patient's identity if necessary
             -> coordinator approves (subject to consent)
             -> only allow-listed clinical evidence is sealed to sponsor
             -> sponsor confirms/requests more data, without identity
             -> clinic controls patient contact and outreach
```

- The existing Clinic UI can show identities to **authorized clinic coordinators** as specified in Section 5.1; encryption **at rest** does not mean clinic staff must never see a patient name. The automated matcher, hub, and sponsor never require identity.
- Do **not** decrypt identities merely to compute match scores, statistics, or candidate packets. Avoid logging the decrypted result.
- Enforce clinic-only authorization on identity-revealing routes; the demo's API-key mechanism is **not** production-grade user authentication. A production version needs per-user RBAC, least-privilege permissions, access audit and secure secrets management.
- Return only the single requested identity record for the selected clinic and patient. Record `identity_accessed`, actor, patient alias, reason, and time **without** copying the identity value to logs.
- The sponsor's decryption of its **candidate packet** is _not_ decryption of the patient's **identity vault**; the sponsor must never receive the clinic's vault key or contact details.

### 24.4 Encryption-specific acceptance tests

- `test_identity_at_rest`: seed a fictional name/email/MRN; assert none appears in raw identity-vault rows, hub DB, audit logs or candidate ciphertext metadata.
- `test_identity_roundtrip`: correct clinic key + patient ID returns original fictional identity.
- `test_identity_wrong_key`: different clinic key fails authenticated decryption.
- `test_identity_wrong_aad`: altered clinic ID or patient ID fails.
- `test_identity_nonce_uniqueness`: encrypting the same identity twice generates distinct nonce/ciphertext.
- `test_match_without_identity_decryption`: instrument the vault; matching 100 patients never calls `decrypt_identity`.
- `test_sponsor_no_identity`: sponsor can decrypt only the allow-listed candidate packet; cannot reveal contact information from it.
- `test_unauthorized_identity_access`: denied role/invalid API key cannot call the clinic identity-reveal operation.

## 25. Where patient updates come from, and what happens when none arrives

Sections 7–8 **already specify** the three rematch triggers, including new FHIR observations, staleness, and trial amendments. The missing operational clarification is **how a clinic obtains that new information**.

1. **Primary production concept:** The clinic connects to its authorized EHR/laboratory workflow; a new `Observation`, `Condition` or medication update is ingested into that clinic's service through the existing `POST /fhir/*` endpoints. A real integration might use FHIR endpoints, subscriptions, integration-engine events or periodic authorized polling, depending on the clinic's EHR capabilities.
2. **Free demo data option:** [Synthea](https://synthetichealth.github.io/downloads.html) publishes **synthetic** FHIR R4 records containing time-varying conditions, observations and medications. Optionally add `scripts/import_synthea.py` to map the sample FHIR records into the existing clinic-only tables. The generated Faker patients and scripted hero remain the primary reliable fixtures; imported records are supplementary and must be screened for supported fields.
3. **Optional FHIR sandbox:** A public FHIR test server such as [HAPI FHIR](https://hapi.fhir.org/) can demonstrate request/response syntax with synthetic test records. **Do not treat it as a dependable source of longitudinal patient history or as a clinical-data source for the live demo**; cache local fixtures, and never upload genuine patient information to it.
4. **No new information?** The system **cannot infer a changed HbA1c or medication merely because three months passed**. It sets affected facts to `UNKNOWN` / `STALE` under the existing recency rules and creates a coordinator follow-up for missing information. It must not announce a new match without a qualifying updated observation.
5. **Patient notification:** Under the original clinic-initiated consent workflow, the clinic can ask for updated information or schedule screening/retesting. Patient-reported changes are hints requiring clinic verification before being treated as validated observations.
6. **History:** Preserve each observation's effective timestamp, ingestion timestamp, unit, source and method; never overwrite history without retaining the prior value. Re-evaluation uses the existing simulated clock and records the before/after criterion transition.

**Demo cases to retain:** (a) HbA1c 11.2 → 9.1 after an actual simulated lab feed creates a new opportunity; (b) 90 days pass with **no** new lab update and the old value becomes stale/`UNKNOWN` rather than a fabricated match; (c) an updated protocol alone can trigger a new review even if the record hasn't changed, provided remaining clinical facts are sufficiently recent.

## 26. Verified HackRx 2026 event context (supersedes outdated event references only)

The original Sections 2, 3, 18 and 21 deliberately remain unchanged, but their **SacHacks VII** tracks, 2–4-person assumption and unconfirmed next-edition language are not the applicable event facts for this build.

Official source: [HackRx 2026 — sachacks.io](https://www.sachacks.io/), checked **November 14, 2026**.

- **Date / venue:** Sunday, **November 15, 2026**, in person at the Betty Irene Moore venue in Sacramento, California.
- **Event format:** The official FAQ describes a **24-hour** hackathon. **Team size: 1–3 people maximum**, not 2–4.
- **Actual award tracks:** Best Translational Science; Best Clinical Impact; Best Biotech Innovation; Health Equity Award; Best Interdisciplinary Hack.
- **Primary target:** **Best Translational Science**, because protocol/data changes can reconnect research with potential participants.
- **Secondary target:** **Best Clinical Impact**, provided the demo measures screening-quality and workflow outcomes honestly. **Health Equity Award** is plausible only with an explicit, tested access/equity component; the core privacy claims alone are insufficient to demonstrate equity impact.
- **Do not assume** the previous SacHacks VII five-minute judging format, three-track submission rule, Figma requirement or 24–36-hour estimate applies. Confirm event-day instructions with HackRx organizers.
- **Pre-built code policy:** Still unconfirmed in the provided materials. Do not assume pre-event implementation is permitted. Follow organizer rules.

**One-day prioritization, without modifying Section 15:** Guarantee a strong single-clinic hero walkthrough (curated eligibility criteria, 3-state matching, timed HbA1c update, coordinator review, local identity encryption) before multiplying services or adding optional external LLM calls. If the full sponsor/hub flow is functional, show sealed-box ciphertext and sponsor confirmation. Keep optional imported Synthea data and live extraction subordinate to the reliable scripted demonstration. The original phase order and cut list remain the implementation authority.

## 27. Additional Definition of Done and implementation checklist

These are **additive acceptance criteria** for the existing phases rather than new phases:

- [ ] **Eligibility source:** Fetch and cache at least one public ClinicalTrials.gov trial; show exact `eligibilityCriteria` source and NCT ID, not only generated text.
- [ ] **Extraction:** `CuratedExtractor` fully runs offline; optional structured-output `LLMExtractor` produces draft-only rules; incorrect source quotations, unsupported logic, and unverified criteria are rejected before hub publication.
- [ ] **Local identity vault:** Each clinic can encrypt/retrieve fake identity records with its own AES-256-GCM key. Plaintext names, phone numbers, MRNs and contact information do not remain in clinic database rows outside the vault.
- [ ] **Separation of duties:** The deterministic matcher can operate without decrypting identities; sponsor candidate packets use the original PyNaCl sealed-box flow and never include contact details.
- [ ] **Data updates:** The hero lab feed triggers `NEW_OPPORTUNITY`; advancing time without new clinical data must never create an unearned eligibility match.
- [ ] **Optional patient-data import:** Use Synthea FHIR R4 if time allows, otherwise use the original Faker seed. Never depend on the public sandbox or live Wi-Fi for judging.
- [ ] **Privacy evaluation:** Automated tests verify AES-GCM authentication failures, sponsor sealed-box isolation, PII guard, consent gates and no identity leakage through hub logs.
- [ ] **HackRx alignment:** The README and submission use the **November 15, 2026 HackRx** award names, correct maximum team size and the exact event's final instructions, not the prior SacHacks VII labels.

### Added implementation files (relative to the original repo layout)

```text
rematch/clinic/identity_vault.py       # AES-256-GCM local identity vault
rematch/extraction/validate.py         # schema/provenance/source-fidelity checks
scripts/extract_trials.py              # optional public trial extraction/caching
scripts/import_synthea.py              # optional synthetic FHIR R4 import
notes/crypto_threat_model.md            # clinic vs sponsor vs hub trust boundaries
docs/extraction_eval.md                # extraction metrics on curated criteria
tests/test_identity_vault.py           # local encryption/authorization tests
tests/test_extraction_sources.py       # extraction quality and publication tests
```

### New `.env.example` keys (append to existing keys; no existing variable is removed)

```dotenv
EXTRACTION_MODE=curated             # curated | llm
OPENAI_API_KEY=                    # optional; public trial text only
OPENAI_MODEL=                      # choose supported structured-output model
CLINIC_IDENTITY_KEY_B64=           # distinct, secret 32-byte key per clinic
CLINIC_IDENTITY_KEY_ID=clinic-a-v1
```

The same environment-key names can exist separately within each clinic process; **do not** load one clinic's AES key into another clinic, the hub, or the sponsor.

## 28. Primary technical references for the new addendum

1. [HackRx 2026 official event, format and prize tracks](https://www.sachacks.io/).
2. [ClinicalTrials.gov data/API information](https://clinicaltrials.gov/data-api/api) and [API v2 studies endpoint](https://clinicaltrials.gov/api/v2/studies).
3. [OpenAI Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses) — schema-constrained public-text extraction; still requires semantic review.
4. [`cryptography` AESGCM documentation](https://cryptography.io/en/stable/hazmat/primitives/aead/) — 256-bit keys, random nonces and authenticated additional data.
5. [PyNaCl public-key `SealedBox` documentation](https://pynacl.readthedocs.io/en/latest/public/) — sponsor-bound encrypted packets; existing design retained.
6. [Synthea synthetic patient records/downloads](https://synthetichealth.github.io/downloads.html) and [generator source](https://github.com/synthetichealth/synthea) — optional FHIR R4 sample data.
7. [HAPI FHIR public test server](https://hapi.fhir.org/) — testing only, not production.
8. [HHS HIPAA de-identification guidance](https://www.hhs.gov/hipaa/for-professionals/special-topics/de-identification/index.html) — pseudonyms and removed names do not independently establish de-identification.

**Final design rule:** The **LLM extracts public trial rules**, **deterministic code evaluates clinic-local medical facts**, **AES-256-GCM protects clinic-local identities**, **PyNaCl protects sponsor-bound evidence**, and **authorized clinic personnel control any identity reveal and patient outreach**. Clinical-trial screening support is never a formal eligibility determination.

## 29. Implemented demo contract clarifications

These clarify the concrete prototype without changing the clinical/privacy boundaries above:

- `Criterion` includes `fasting_required: bool = False` so the Section 7.4 verification rule can be represented explicitly.
- `AggregateSignal` includes `min_cell_size: int` and `suppressed: bool`. Count fields become null when suppressed. If any nonzero cell is below the threshold, the entire row is suppressed to avoid recovering a hidden count by subtraction. These fields contain no patient information.
- Referral retrieval includes `retracted` and a fixed-enumeration `retraction_reason`; a retracted referral has an empty ciphertext field. Reasons are `withdrawn`, `data_changed`, `protocol_changed`, or `clinic_reset`. Only routing metadata is added, never identity or clinical facts.
- The hero follow-up fixture also includes refreshed BMI and a clinic-verified pregnancy assessment, alongside HbA1c and eGFR. Otherwise the original recency windows would legitimately block the 90-day demonstration.
- Historical states are retained on a legitimate A→B→A cycle. Exact repeated evaluation of unchanged inputs remains a no-op; event identity also includes the previous result hash.
- Once evidence becomes stale or a protocol version changes, the old packet is retracted and coordinator review is required before resending. Retractions persist in an outbox if the hub is temporarily unavailable.
- The real cached NCT03548935 record is completed and is shown for public-source provenance only. It is not published as a recruiting matching protocol. Optional OpenAI extraction produces downloadable drafts for review; automatic real-protocol publication is outside this prototype.
- The Clinic reset button resets the selected clinic and retracts its packets. The launcher's `--reset` restores the entire network. The committed `DEMO.md` is the short setup/judging guide; the local backup recording lives in ignored `artifacts/`.
