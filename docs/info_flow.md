# Information flow and safeguards

How data moves through ReMatch, and what the product refuses to do. This matches the current central, patient-initiated architecture (`CHANGES.md`, `rematch/service.py`, `notes/crypto_threat_model.md`). All patients, records, payments, and introductions in the demo are synthetic.

## End-to-end flow

```text
Study team                ReMatch                         Patient / PCP
──────────                ───────                         ─────────────
List study / NCT
  │
  ├─ public/synthetic text ──► LLM extract + brief
  │                            + deterministic validation
  │                            + risk route (LOW|HIGH|UNKNOWN)
  │
  └─ publish listing ◄──────── validated study spec

                          ◄── screening permission (versioned)
                          ◄── simulated Epic / record auth
                          ◄── import FHIR-shaped fixture
                               (encrypted, retained centrally)

                          deterministic Python match
                               POTENTIAL_MATCH | NEEDS_INFO | NOT_MATCHED

          LOW + source support ──► patient sees actionable card
          HIGH / UNKNOWN ───────► PCP discussion queue
                                      │
                                      └─ discussion completed
                                         (not eligibility)

                          patient requests introduction
                               exact disclosure preview
                               (name, contact, screening summary,
                                named PI/site, versions)
                                      │
                                      └─ separate patient auth

Named team only ◄──────── authorized packet
  acknowledge /
  invite formal screening /
  record enrollment outcome
```

## What moves where

| Step | Moves | Does not move |
| --- | --- | --- |
| Study generation | Public / synthetic study text → LLM → rules + brief | Patient names, contacts, IDs, FHIR, match evidence → LLM |
| Matching | Encrypted clinical facts → central matcher (trusted processor) | Eligibility or enrollment decisions by the model or ReMatch |
| Discovery | LOW matches → patient profile | Full HIGH/UNKNOWN card before assigned-PCP discussion |
| Introduction | After preview + auth: name, selected contact, relevant screening summary → that one PI/site | Full chart, DOB, address, unrelated history by default; any team browsing candidates before auth |
| Doctor review | Assigned patients + brief + match reasons for discussion cases | Formal eligibility; permission to disclose identity |

## Layered permissions

These are separate, versioned, and revocable:

1. **Research matching** — keep authorized records for ongoing screening.
2. **Simulated record access** — allow imports of the local synthetic fixture.
3. **PCP discussion** — required only for HIGH / UNKNOWN before introduction.
4. **Per-introduction disclosure** — exact packet to one named team; screening or discussion alone is never enough.

## Safeguards (product rules)

- **Fail-closed risk.** `LOW` needs explicit source support (or a labeled synthetic fixture). Missing or conflicting evidence routes as `UNKNOWN` through the PCP.
- **No PHI in prompts.** LLM prompts are an allow-list of public/synthetic study fields. Match explanations are local rule results/templates.
- **No pre-auth candidates.** Research teams have listings and authorized introductions only — no patient directory.
- **Minimum necessary packet.** Preview expires and is bound to patient, recipient, study version, and record version. Changing records or study text invalidates pending previews.
- **Encryption and access.** AES-256-GCM with patient/type/schema authenticated data. Principal-bound demo credentials: patient self, assigned doctor, named team.
- **Withdrawal.** Disconnect stops future imports. Stop matching retracts introductions and removes retained clinical/match data. Delete also removes identity and derived payloads; earned onboarding credit remains. Software cannot erase a recipient’s prior knowledge.

## What ReMatch is not

- Not formal eligibility, study-specific informed consent, or enrollment (research site).
- Not a production Epic, HIPAA, or IRB compliance claim.
- Not a physician referral bounty or enrollment commission.

## Code map

| Concern | Path |
| --- | --- |
| Orchestration (permissions, import, route, preview, auth, withdraw) | `rematch/service.py` |
| Role-gated HTTP API | `rematch/api.py` |
| AES-GCM vault | `rematch/common/crypto.py` |
| Deterministic matching | `rematch/clinic/matching/engine.py` |
| LLM (source-only prompts) | `rematch/extraction/llm.py` |
| Risk fail-closed | `rematch/extraction/validate.py` |
| Patient / doctor / team UI | `frontend/src/Patient.tsx`, `Doctor.tsx`, `Team.tsx` |
| Threat / consent boundaries | `notes/crypto_threat_model.md` |
