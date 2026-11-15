# ReMatch pivot — implementation handoff

**Date:** November 15, 2026. **Status:** proposed implementation specification; the pivot has not been implemented by creating this document.

This is a standalone handoff for a new Codex session. The user requested this file only in the planning session. On a subsequent request to implement the pivot, use this document as the product authority wherever it conflicts with `PLAN.md`, the existing README, or existing behavior. Read applicable `AGENTS.md` instructions and inspect current code before editing. Keep unrelated user changes.

## 1. The product in one paragraph

ReMatch reduces routine research-screening work for a primary care physician (PCP). A principal investigator (PI) or study team lists a study. A patient independently opts into screening and authorizes a **simulated** Epic/FHIR connection. ReMatch retains the authorized synthetic records, converts study requirements into rules using an LLM, and evaluates those rules with deterministic Python. A potential match to a supported low-risk study appears directly in the patient's profile. A higher-risk or unknown-risk opportunity goes through a brief PCP discussion first. The patient then explicitly authorizes an introduction to the study team. The PI/site handles detailed questions, study-specific informed consent, formal eligibility, and enrollment.

**Explain it as:** “Connect your records once. Find relevant studies. Get your doctor's help when a discussion is needed. Choose whether to meet the research team.”

## 2. Confirmed user decisions

| Topic | Decision |
| --- | --- |
| Main objective | Move routine work from the PCP to ReMatch, the patient, and the study team. |
| Roles | Patient; PCP, the patient's usual doctor; PI/study team, the research site running the study. A PI is not synonymous with a trial's financial sponsor. |
| Study input | ClinicalTrials.gov requirements, supplemented by identifiable study-source documents when needed for risks, benefits, visits, or compensation. |
| Extraction and briefs | An LLM generates structured requirements and study briefs. Use the OpenAI key already in local `.env`; do not request it in chat or expose its value. |
| Patient evaluation | Deterministic Python screening against the structured requirements. An LLM does not make formal eligibility or enrollment decisions. |
| Record location | ReMatch may retain patient records centrally for ongoing matching under the patient's permissions. This replaces the old clinic-local architecture. |
| Epic/FHIR | Both are simulated for this hackathon. No real Epic connection, real patient records, or production EHR access. |
| Routing | Supported low risk: patient directly. Higher or unknown risk: PCP discussion first. Compensation does not determine this route. |
| Benefits and payment | Keep research importance, possible individual health benefit, and financial compensation separate. They are patient information, not interchangeable “reward” scores. |
| Business model | Simulated flat study-listing fees. No enrollment-based doctor commission or physician referral bounty. |
| Patient incentive | A simulated, modest payment for onboarding time; not a reward for agreeing to consent or enrolling. |
| Contact handoff | Separate, explicit patient permission to share name, preferred contact, and a relevant screening summary with one named study team. |
| Cleanup | Remove obsolete features and obsolete workflow gates; do not ship the old and new products side by side. |

These answers are settled. Do not ask the user to reconfirm them during implementation.

## 3. What changes from the existing build

| Existing behavior or component | Required replacement |
| --- | --- |
| Clinic A/B perform local matching; hub routes ciphertext | One central ReMatch backend stores authorized synthetic records and performs screening. |
| Three separate role apps, six processes, clinic selector | One Streamlit app with a simple role switch and guided demo; one FastAPI backend. Keep the current Python stack. |
| Every opportunity requires coordinator approval, sponsor confirmation, and clinic release | Route potential matches by study risk. Low-risk opportunities skip PCP review and pre-discovery PI confirmation. |
| Patient must wait for a clinic research invitation | Patient can onboard and initiate research preferences and simulated record connection. |
| Sponsor gets an anonymous candidate packet before the patient chooses a study | No candidate-level disclosure to a study team until that patient authorizes an introduction. |
| Sponsor can never receive identity | The selected PI/site may receive explicitly authorized name/contact information at introduction time. |
| Hub never reads clinical records | ReMatch is now a trusted data processor. It can read authorized clinical facts for matching. Remove the old claim. |
| Human-verification checkbox is mandatory to publish extracted rules | LLM generation/review plus programmatic validation for the synthetic prototype, accurately labeled. Do not pretend a human clinician verified model output. |
| “High risk, high reward first” | Separate risk, relevance, importance, possible benefit, and compensation. Never promote a study because it is riskier, pays more, or bought a listing. |
| Many technical menus | Three plain workspaces: “My studies,” “Doctor review,” and “Study team.” Technical detail is secondary. |

Keep the deterministic three-state engine, unit handling, source provenance, consent enforcement, encryption primitives, longitudinal reassessment, reproducible seed, clock/reset utilities, and useful tests. Refactor them around the new architecture.

## 4. New journey and routing rules

### A. Study-team listing

1. Study team creates a listing tied to a study/NCT ID and a specific PI/site. Store the registry's sponsor separately if present.
2. Simulate a flat listing payment. Clearly label the action and receipt “Demo payment — no charge.” Payment never buys favorable clinical ranking or waives validation.
3. Fetch/cache the public source; retain original eligibility text, recruitment status, version/hash, and retrieval metadata.
4. Run the LLM extraction, brief-generation, and model review workflow in Section 5.
5. Publish only source-validated material. A completed/closed study is not an active recruiting listing. Keep the existing completed NCT03548935 cache as a source example, not a live opportunity.

### B. Patient onboarding and retained records

1. Patient opens their own profile and sees a short explanation of matching, record use, choices, and withdrawal.
2. Record screening permission and a separate simulated record-access authorization, each versioned and revocable.
3. “Connect my records — simulated Epic” opens a clearly fake authorization flow and imports a local synthetic FHIR fixture only after permission. Never collect a real MyChart password or imply Epic endorsement/certification.
4. Persist the authorized synthetic records centrally, with provenance and history. Match automatically; do not create a PCP task for every imported record or every failed criterion.
5. Show any onboarding-time credit separately from consent. Declining consent must still be possible without losing a credit already earned for time spent. No real payment is sent.

### C. Screening and discovery

Use these engine results and plain-language UI labels:

| Engine result | UI label | Action |
| --- | --- | --- |
| `POTENTIAL_MATCH` | “May fit this study” | Apply the risk route below. |
| `NEEDS_INFO` | “More information needed” | Show the missing information without calling it an eligible match. No automatic introduction. |
| `NOT_MATCHED` | “Requirements not currently met” | Keep reassessment history; do not create a routine PCP referral task. |

For a current potential match to an active study:

| Operational risk route | Destination | PCP requirement |
| --- | --- | --- |
| `LOW` with adequate source support | Patient's study profile | None before discovery or patient-authorized introduction. |
| `HIGH` | Assigned PCP's focused discussion queue | Discussion must be recorded before introduction is enabled. |
| `UNKNOWN`, conflicting classification, or insufficient source evidence | PCP review queue | Never silently treat missing risk information as low risk. |

Apply this rule regardless of patient payment or claimed study benefit. Include low-risk/high-benefit and higher-risk/low-or-uncertain-benefit cases in tests. These labels are demo routing categories, not a new regulatory risk determination.

**Conservative UI default for a detail not separately specified by the user:** while PCP discussion is pending, show the patient a neutral “Your doctor can help you review this opportunity” status. Release the full actionable card after discussion; do not send promotional prompts or enable contact sharing beforehand. The discussion supports a voluntary choice, not persuasion to join.

The PCP receives a brief and actions such as “Discussion completed,” “Need more information,” and “Not appropriate to pursue now,” with an optional short note. The PCP does not re-enter the entire chart, rewrite trial criteria, or declare final study eligibility. A patient without an assigned PCP can still view supported low-risk opportunities; higher/unknown-risk cases remain pending, with a clear instruction to arrange review rather than silently bypassing it.

### D. Patient-controlled introduction

1. Show PI/site identity and public contact information to the patient. Public study contact details are not themselves a disclosure of patient identity.
2. Offer “Request an introduction.” For higher/unknown-risk cases, enforce the completed-discussion gate on the backend as well as the UI.
3. Preview the exact patient fields, clinical summary, recipient, purpose, and source-record/study versions that would be shared.
4. Patient separately confirms permission for that one introduction. Screening permission or simulated Epic authorization alone is insufficient. PCP discussion alone is insufficient.
5. Create an introduction record; make the authorized packet available only to that study team. Add the study team's contact details and next step to the patient's profile.
6. PI/site can acknowledge, request further information, invite to formal screening, or close the introduction. Further record/field disclosure requires the appropriate additional patient permission.
7. Record enrollment only as an explicit, simulated PI/site outcome. Interest, introduction, discussion, and screening invitation are not enrollment. No event triggers a physician payout.

All notifications, introductions, appointment arrangements, and payment receipts remain in-app simulations. No real email/SMS, external referral, appointment, or money transfer is sent.

## 5. LLM responsibilities, sources, and boundaries

The user selected an **LLM**, rather than mandatory manual PI verification, to generate/review the rules and brief. Implement this choice for the synthetic prototype. Do not preserve the old mandatory “mark every criterion human verified” UI gate under another name.

The pipeline is:

`Public/source study documents → LLM extraction and brief → model consistency review + deterministic checks → publishable demo study specification → deterministic patient screening`.

- Read `OPENAI_API_KEY` from `.env` server-side. Respect a configured `OPENAI_MODEL`; if missing, determine a currently supported Structured Outputs model from official documentation and record the choice in configuration. Never print keys, copy `.env` into documentation, or commit secrets.
- Only public study text and explicitly synthetic study-source fixtures go to the LLM. Patient names, contacts, medical records, tokens, patient IDs, and patient-specific evidence stay out of prompts. Compose “why this may fit you” from local rule results/templates.
- Preserve exact source quotations and source locations for criteria and every factual brief claim. Distinguish registry information from supplementary study-team source documents. Treat source text as data, not instructions for tools or secrets.
- ClinicalTrials.gov eligibility text alone is not sufficient evidence for all risks, possible benefits, time commitments, or payments. Missing facts must say “Not provided in the available study information.” Do not fill them from general drug knowledge or model memory.
- Validate the schema, registered fields, bounds, units, inclusion/exclusion polarity, source quotations, supported logic and protocol coverage. Preserve unsupported/ambiguous clauses as `unmapped`/manual follow-up so they cannot silently disappear from screening.
- Model review is an additional automated check, not independent clinical certification. A high confidence score is not proof of safety or correctness.
- Store extraction state such as `DRAFT`, `VALIDATED_FOR_DEMO`, or `BLOCKED`, plus validation errors, model ID, prompt/schema versions and source hash. Do not reuse `review_status="verified"` to imply human review that never occurred.
- The LLM may suggest a risk route with source evidence. `LOW` needs an explicit source-supported low-risk designation or a deliberately labeled synthetic fixture designation; an LLM's unsupported inference cannot establish low risk. Otherwise route as `UNKNOWN` through the PCP. Do not infer “safe” from a study title, observational label, trial phase, or payment amount alone.
- Cache successful validated output by source/model/prompt/schema versions. Changed source text invalidates the rules, brief and risk route. Reassess affected patients and invalidate uncompleted actions bound to superseded versions.
- Show a concise “AI-generated study summary” label and access to the original source. Production clinical validation remains future work, not something this prototype claims to have completed.
- Make a small live generation path work with the local key; use cached, validated synthetic examples for offline judging. On API failure, surface the failure and preserve valid cached data. Never pretend a cached fixture was a successful live model call.

The five-line brief contains exactly these headings:

1. **Purpose:** What the study is trying to learn.
2. **What participation involves:** Main procedures, visits and time commitment.
3. **Main risks and uncertainties:** Supported risks/side effects and unknowns.
4. **Possible benefits:** Potential individual benefit, if stated; explicitly no guaranteed benefit. Keep broader research importance separate.
5. **Costs and compensation:** Patient costs, reimbursement and compensation as distinct amounts/terms where known.

Keep the source-grounded brief reusable. Show personal match reasons and the introduction button separately. Do not generate a sales pitch about “why you should join.”

## 6. Data, consent, and privacy architecture

### Central ReMatch service

Use one FastAPI service and one SQLite database for the prototype. One Streamlit app talks to this backend. Keep backend API credentials and role checks; bind locally. Remove the hub/clinic federation dependency from startup.

Reuse AES-GCM primitives for a central identity vault and encrypted retained clinical payloads. Bind ciphertext to patient ownership, record type and schema version using authenticated data. Keep keys outside SQLite and source control. The matcher can decrypt authorized clinical facts in the backend while still operating without decrypting identity records. Do not persist plaintext duplicates of imported FHIR bundles or normalized clinical snapshots in logs, caches, audit rows or secondary tables while claiming those records are encrypted at rest.

The old `clinic_id`-bound vault and independent clinic keys cannot simply be relabeled. For the demo, use a new runtime database/schema and a deliberate reseed; do not silently reinterpret old ciphertext or sweep arbitrary files. Stop the previous processes before a reset. Existing runtime state is synthetic, but any destructive reset must be explicit in the command/UI.

### Minimum concepts to represent

| Concept | Required contents |
| --- | --- |
| Patient/profile | Internal ID, assigned PCP if any, encrypted identity/contact record, preferences. |
| Patient permissions | Separate versioned screening permission, simulated record authorization, and per-introduction disclosure permission; scope, recipient, time and revocation state. |
| Clinical record | Patient ownership, encrypted FHIR-shaped payload/history, source/effective/ingestion times, supported normalized facts. |
| Study specification | Study/NCT ID, original source/version, structured criteria, generated brief, validation/provenance metadata. |
| Study listing | Listing ID, study version, PI/site identity/contact, owner, recruiting status, simulated listing-payment state, risk route/evidence; separate importance/benefit/compensation information. |
| Match | Patient/listing/version, three-state result, explanations, missing/stale facts, history and route. |
| PCP discussion | Match/version, assigned PCP, pending/completed/deferred outcome, source brief version, note and time. |
| Introduction | Patient/listing/PI/site, exact disclosure snapshot, patient authorization/version, delivery/acknowledgment state, screening/enrollment outcome. |
| Audit/outbox | Actor, action, record references, purpose, consent/version and delivery state; no copied medical records, identity values, API keys or tokens. |
| Demo payment | Listing charge or patient onboarding-time credit, configurable synthetic amount/currency, simulated state; no doctor commission type. |

Use separate state machines for screening, discussion, introduction and enrollment. A single overloaded `pipeline_state` must not force low-risk cases through removed gates.

Suggested introduction states: `NOT_REQUESTED → AWAITING_PATIENT_PERMISSION → AUTHORIZED → SHARED → ACKNOWLEDGED → SCREENING_INVITED`, with explicit `DECLINED`, `WITHDRAWN` and `CLOSED` paths. `ENROLLED` is a separate PI/site-reported outcome. Discussion is a prerequisite only where routing requires it.

### Explicit data-sharing contracts

- Internal patient/PCP access is restricted to that patient or the patient's assigned PCP. Study teams cannot browse the central patient directory or raw records.
- Before introduction authorization, a study team sees no candidate-level patient record. Public study information is available independently.
- After valid authorization, an allow-listed introduction packet may contain name, the chosen contact method/value and only the relevant screening summary that was previewed. Do not attach the full chart, DOB, address or unrelated history by default.
- Retain a pseudonymous reference where useful, but do not claim an introduction with name/contact is anonymous or de-identified.
- The existing blanket PII blocker must be replaced with purpose-specific contracts: anonymous/screening outputs continue to exclude identity; an authorized introduction deliberately permits only its disclosed identity fields. Do not disable privacy checks globally to make introductions work.
- Encrypt retained data and protect recipient access. The old sponsor sealed-box relay and public-key registration are not prerequisites for this central demo. If application-level delivery encryption is retained, it is an internal safeguard, not the old product narrative.

### Retention and withdrawal

Retain records to support reassessment while the corresponding permission remains active. “Disconnect records” stops future simulated imports; “Stop research matching” stops matching and new disclosures. Revoke pending introductions and PCP tasks when required. Provide a separate “Delete my stored records” control to remove retained identity/clinical payloads and derived caches, with only minimal non-identifying audit information retained. Do not infer consent to indefinite retention after withdrawal.

Withdrawal must not remove an earned onboarding-time credit or affect regular care. Simulated shared introductions receive a withdrawal/retraction status, retried through an outbox if necessary. Explain that software cannot make an external recipient forget information already disclosed. Do not claim production retention, HIPAA, IRB or Epic compliance.

## 7. Remove obsolete features completely

“Stale features” in this pivot means superseded product features. Clinical results that are too old must still become `UNKNOWN`/`STALE`; removing that engine behavior would fabricate screening certainty. Keep that safeguard behind plain-language explanations instead of a standalone dashboard.

Remove from normal startup, primary UI, active endpoints and current documentation:

- Clinic A/B selection, clinic federation, clinic registration/polling and cross-clinic aggregate charts.
- The separate hub-as-ciphertext-router service and the claim that the central platform cannot read clinical records.
- Mandatory coordinator approve/send, pre-discovery sponsor confirmation and clinic release for every match.
- The clinic-initiated research-invitation requirement for patient onboarding.
- Automatic pre-permission candidate packets and study-team access to candidate lists before patient authorization.
- Sponsor terminology where the actor is actually the PI/site. Keep genuine registry sponsor metadata correctly named.
- Six-process/three-window judging instructions and prominent technical routing/network-inspector screens.
- Standalone freshness, data-reuse, small-cell-feasibility and simulated reminder dashboards. Keep only underlying behavior needed for correct matching or a secondary explanation.
- Physician referral payouts, enrollment commissions, real payment processing and compensation-based ranking.
- The old required human-verification checkbox when LLM processing is the chosen prototype workflow.
- Old state transitions, fixtures, screenshots, video references, tests and scripts that demonstrate or enforce the replaced pipeline. Replace useful tests with equivalent tests for the new rules; do not simply delete safeguards to get green tests.

Historical material may be clearly archived, but the new launcher/UI must not accidentally expose or start the old product. Do not package the old `sachacks-essentials.zip` or old backup video as if they demonstrate the pivot; create fresh artifacts after implementation if requested/needed.

## 8. UI and scope constraints

- One browser URL and one guided story. Use a clear role switch for the demo; label fake accounts as a simulation rather than implying production login.
- **My studies:** short consent/record-connection flow, relevant opportunity cards, clear waiting states, introduction permissions, contact/next steps, withdraw/delete controls.
- **Doctor review:** only cases requiring discussion, a five-line brief, local match reasons on demand, and a small number of discussion actions. Group work by patient; avoid duplicate tasks on identical reassessment.
- **Study team:** listing and simulated fee, public-source import/generation, validation status, authorized introductions and follow-up outcomes.
- Money is informational, visually separate from health benefit, and never a large “reward” badge. Listing fees do not affect discovery ordering. Use a stable deterministic order for the demo; any later relevance ranking must explain its inputs and exclude payment/risk as promotional boosts.
- Explain PCP and PI in the interface: “Your doctor” and “Research team.” Put raw criteria, FHIR JSON, audit details, model/source metadata and technical diagnostics under “Show how it works.”
- Preserve the existing HbA1c reassessment as an optional short proof of the name ReMatch, not a prerequisite for understanding the new onboarding/introduction journey.
- No real Epic OAuth, production authentication project, cloud deployment, Stripe checkout, real messages, automatic booking, real patient import, or new frontend stack. Python/FastAPI/Streamlit/SQLite remain sufficient.

## 9. Map the existing repository to the new build

Inspect these paths; reuse behavior deliberately rather than building a second implementation beside it:

| Current files | Action |
| --- | --- |
| `rematch/common/schemas.py` | Add the separated listing, permission, discussion and introduction contracts; replace human-only publication semantics. |
| `rematch/clinic/matching/*`, `common/fields.py`, `common/units.py` | Preserve/refactor the pure deterministic engine, unknown/stale/unit handling and synthetic tests. Moving modules is optional if active architecture is unambiguous. |
| `rematch/extraction/ctgov.py`, `llm.py`, `validate.py` | Extend into the source-grounded LLM pipeline, brief generation, automated validation and risk evidence. |
| `rematch/clinic/identity_vault.py`, `common/db.py`, `common/crypto.py` | Reuse encryption/storage primitives with the new central ownership/AAD model; retire unused relay-only machinery. |
| `rematch/clinic/main.py`, `service.py`, `outreach.py`, `deid.py` | Replace clinic invitation/release/coordinator gates with central permissions, routing, discussion and consented introduction. Old routes must not bypass new gates. |
| `rematch/hub/*`, `clinic/network.py` | Retire federation-only service wiring and fold reusable study registry behavior into the central backend. |
| `rematch/ui/*` | Replace separate apps with one role-aware Streamlit entry point and small shared components. |
| `scripts/run_demo.py`, seed/reset helpers, `.env.example` | Keep familiar launch/reset commands, but start the new backend/UI only. Preserve useful Windows startup progress, health checks, process isolation and cleanup. |
| `scripts/check_demo.py`, `record_demo.py`, `tests/*` | Replace old walkthroughs and contract assumptions; retain valid engine/encryption/provenance tests. |
| `README.md`, `DEMO.md`, `PLAN.md`, `docs/*`, `notes/*` | Make the pivot the documented default; label the old plan historical/superseded and replace misleading privacy/integration/eligibility claims. |

Do not read `.env` values into chat/tool output. Use configuration loading and presence checks without printing secrets. Existing generated keys, runtime databases and the old archive are local artifacts, not application source to redistribute automatically.

## 10. Implementation order and completion checks

1. **Replace the architecture and contracts:** central backend/store, one UI entry point, separated states and permissions. Explicit reset seeds the new schema. Verify health/start/stop before adding features.
2. **Patient onboarding and simulated FHIR:** permission-gated import, encrypted persistence, disconnect/withdraw/delete behavior. Confirm import cannot run before authorization.
3. **Study-team listing and LLM processing:** simulated fee, public-source cache, actual key-backed generation path, cached offline fixtures, source/schema checks and honest risk/brief labels. An unavailable API must not fabricate success.
4. **Screening and risk routing:** retain deterministic engine; implement low-risk direct discovery and higher/unknown-risk PCP discussion. Add regression tests before exposing introduction actions.
5. **Consented introduction and PI follow-up:** exact preview, scoped authorization, recipient-bound access, idempotent delivery, withdrawal and explicit simulated enrollment outcome. No physician payout.
6. **Remove old features and finish the demo:** delete/retire obsolete wiring and bypass routes, replace navigation/docs/walkthroughs, run the complete demo from the UI, and verify a clean setup plus reset.

Required acceptance scenarios:

- A new patient can onboard without a clinic invitation; rejecting permissions still leaves an understandable usable profile and does not forfeit earned time compensation.
- Simulated Epic import is blocked without valid record authorization; reloaded data remains available for authorized reassessment without pretending a real Epic session exists.
- No patient data reaches an LLM. Failed quotations, invalid thresholds, unsupported logic and incomplete extraction cannot silently produce an actionable potential match.
- Known supported low risk produces a patient opportunity and **zero PCP discussion tasks**, regardless of high/low compensation or possible benefit.
- Higher risk or unknown/unsupported risk creates a PCP discussion case; a backend introduction attempt before discussion fails. An unassigned PCP does not bypass this gate.
- Unknown/missing/expired clinical facts remain unknown, and a closed study cannot generate an actionable introduction.
- The five-point brief uses source evidence, distinguishes benefit from money, marks missing information and does not guarantee benefit or final eligibility.
- A study team sees no patient directory, candidate record, name/contact or screening summary before that patient's specific authorization.
- After discussion when required and explicit authorization, only the named PI/site receives the exact approved fields. Another site, another patient, a stale authorization or an old study version cannot reuse the permission.
- Introduction delivery is idempotent. Interest/intro/PI acknowledgment does not auto-enroll the patient. Recorded enrollment never creates doctor compensation.
- Withdrawal blocks future matching/imports as applicable, closes pending actions, persists any needed retraction and preserves earned time credits. Deleting records also removes derived identifiable caches.
- Source/protocol/risk changes and new clinical information invalidate affected pending actions and trigger reassessment without duplicate tasks or automatic expanded disclosure.
- The launch command starts only the new backend and one UI; old clinic selectors, mandatory release gates and obsolete privacy claims are absent.
- Tests check retained encryption/authentication and role access, both routing paths, unknown-risk fallback, consent boundaries, compensation independence, source fidelity, reassessment and record deletion. Live LLM success and offline/cached success are reported separately.

## 11. Short judges' demonstration

Prepare synthetic fixtures with declared provenance for a low-risk listing and a higher-risk listing, a patient profile and a PCP assignment. Display all amounts and risk designations as demo information. Unknown risk gets its own fallback case.

1. Research team lists a study, sees a simulated listing receipt and a source-grounded LLM brief/rules.
2. Patient chooses matching permissions and connects simulated Epic records via a local FHIR fixture.
3. Show the low-risk opportunity directly in “My studies”; the doctor's queue stays unchanged.
4. Show the higher-risk opportunity awaiting a short doctor discussion with the same five-line brief.
5. Complete the discussion in the doctor view; patient previews and authorizes one introduction.
6. Research team sees only that authorized introduction; patient sees the research team's contact and next step. Demonstrate withdrawal if time permits.
7. Optionally show one changed synthetic lab result creating a new opportunity, with its source and timestamp, rather than inferring improvement from elapsed time.

Measure software events such as PCP tasks created in this demo and introductions authorized. Do not claim measured clinical effectiveness, guaranteed benefit, proven physician time savings or improved enrollment without evidence.

## 12. Background references and production limits

These explain the choices; they do not turn this hackathon prototype into an approved clinical or payment system:

- [AMA: Fee Splitting](https://code-medical-ethics.ama-assn.org/ethics-opinions/fee-splitting) — physician research-referral payments raise a direct ethics concern; the accepted prototype removes that commission model.
- [FDA: Payment and Reimbursement to Research Subjects](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/payment-and-reimbursement-research-subjects) — distinguish payment from benefit and avoid undue influence; no actual compensation program is approved by this specification.
- [FDA: Recruiting Study Subjects](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/recruiting-study-subjects) — source-grounded recruitment information, balanced risks/benefits and applicable review requirements matter. LLM generation does not replace those real-world requirements.
- [Epic: FHIR interfaces](https://open.epic.com/Interface/FHIR) — real FHIR access requires integration/authorization work. This project only simulates the connection and does not collect real credentials.
- [ClinicalTrials.gov API](https://clinicaltrials.gov/data-api/api) — public study-source provenance, not a guarantee that eligibility text contains the full consent or safety information.

Real deployment would require appropriate clinical, institutional, privacy, security, consent and legal review. In this build every patient, imported record, permission interaction, risk designation, payment, introduction and enrollment outcome is synthetic/simulated; public study information and configured public-text LLM calls may be real and must be labeled accurately.
