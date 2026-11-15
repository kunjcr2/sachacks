# ReMatch

Connect your records once. Find relevant studies. Get your doctor's help when a discussion is needed. Choose whether to meet the research team.

ReMatch is a synthetic research-screening prototype with one FastAPI backend, one SQLite database, and a React/TypeScript frontend. Patients onboard themselves, grant separate screening and simulated record-access permissions, and import a local FHIR-shaped fixture. Deterministic Python evaluates study requirements. Supported low-risk potential matches appear directly; higher or unknown-risk opportunities require a discussion with the patient's assigned usual doctor (PCP). Patients separately preview and authorize each introduction to a named principal investigator (PI) and research site.

Requires Python 3.11+ and Node.js 20.19+ or 22+. Setup installs the locked Python and frontend dependencies. The launcher builds React only when its source changes.

```powershell
python scripts/setup.py
.\.venv\Scripts\python.exe scripts/run_demo.py --reset
```

Open **http://localhost:8000**. Switch between **My studies**, **Doctor review**, and **Study team**. These are fake demo accounts, not production authentication. The backend binds to 127.0.0.1:8000. Ctrl+C stops the backend. No Node server runs during normal use.

The first launch creates a new `runtime/rematch-central-v1.sqlite` and central keys/credentials in `.keys/`. `--reset` explicitly clears only the new central database after checking the old demo ports are stopped. Existing clinic databases and keys are never migrated or reinterpreted. Stop a previous launcher before starting this version.

[Walkthrough and verification commands](DEMO.md) | [Product specification](CHANGES.md) | [Data and consent boundaries](notes/crypto_threat_model.md) | [Extraction checks and limits](docs/extraction_eval.md)

Public or explicitly synthetic study text can go through OpenAI Structured Outputs, model consistency review, and deterministic source/schema checks. Configure `OPENAI_API_KEY` and `OPENAI_MODEL` in local `.env`; neither is exposed in the interface. Patient records, names, contacts and evidence never enter model prompts. Source-grounded briefs use five exact headings and preserve quotations. Missing facts stay missing; unsupported requirements block publication. The prototype deliberately supports a narrow atomic rule grammar rather than guessing at complex protocols.

Four validated synthetic study fixtures work offline, labeled **offline synthetic fixture**, with low, high, unknown and HbA1c reassessment cases. Offline fixtures are not represented as successful live calls. API failures preserve valid cached material and report failure. The completed public NCT03548935 cache is retained as a source example, never a recruiting opportunity.

Identity/contact, retained clinical bundles, clinical screening results, discussion notes and introduction snapshots are encrypted with AES-256-GCM and patient/type/schema binding. ReMatch is the trusted processor and can decrypt authorized records centrally. Principal-bound demo API credentials enforce patient, assigned-doctor and named-team access. These local demo controls are not a production login or security certification.

Research teams see no patient directory or pre-permission candidate records. After an explicit, version-bound authorization they receive only the exact previewed name, selected contact and relevant screening summary. Changing records, permissions, source or study versions invalidates pending actions. Disconnect stops future imports; stop matching retracts introductions and removes retained clinical screening data; delete also removes identity and derived payloads. Earned onboarding-time credit remains. Retraction cannot make an external recipient forget information already disclosed.

All patients, Epic authorization, risk-routing designations, listing fees, onboarding credits, introductions and enrollment outcomes are synthetic or simulated. No real login, health-record import, message, referral, booking, charge, payout or money transfer occurs. Fees, compensation, research importance and possible individual benefit are separate; payments never promote a study or produce doctor commissions. Formal eligibility, study-specific informed consent and enrollment belong to the research team. Clinical validation and production privacy/security review remain future work.

The old federation, separate role apps, coordinator release gates, automatic candidate packets, stale screenshots and old walkthroughs have been removed. `PLAN.md` is explicitly historical. The old archive is preserved locally under ignored `artifacts/`, not shipped as the new demo.

For frontend development: `npm run dev --prefix frontend` with the backend running. Vite proxies `/api` to localhost:8000. The normal launcher uses the compiled frontend and runs only FastAPI. Streamlit has been removed.
