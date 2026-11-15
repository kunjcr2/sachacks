# ReMatch — submission draft

**Tagline:** Discover. Reassess. Re-engage. Retain.

**Pitch:** Being screened out of research once should not mean being forgotten. ReMatch takes another look when clinical facts or trial protocols change, while keeping identities and medical records inside the clinic.

**What it does:** Two synthetic clinics evaluate public, human-verified study rules locally. When a previously unmet requirement may now be met, a coordinator receives a before/after review task. Approved, minimum-necessary evidence is encrypted to the sponsor; the hub sees only routing metadata and ciphertext. Sponsor confirmation returns to the clinic, which controls patient outreach. Patients decide whether to discuss a study and can withdraw.

**Demo:** PX-82914 has HbA1c 11.2%, outside a fictional trial's 7.5–10.0% range. Ninety days alone produces stale information, not a guessed improvement. A simulated follow-up feed provides HbA1c 9.1% and refreshed assessments, triggering a new coordinator review. Demonstrate approval, ciphertext routing, sponsor confirmation, patient choice and withdrawal.

**Built with:** Python, FastAPI, SQLite/SQLAlchemy, Pydantic, Streamlit, Plotly, Faker, AES-256-GCM and PyNaCl sealed boxes. Optional OpenAI Structured Outputs extracts only public trial text into unverified drafts; deterministic Python evaluates clinical facts.

**What is demonstrated:** Longitudinal reassessment, missing/stale information handling, unit normalization, coordinator review, separate clinic databases, encrypted identity storage, per-trial pseudonyms, sealed evidence routing, consent gating, patient choice and retractions. Tests measure software behavior, not clinical effectiveness or recruitment impact.

**Award fit:** Best Translational Science; potentially Best Clinical Impact. No claim of demonstrated health-equity outcomes. Check final HackRx submission rules and categories with the organizers.

**Honest limitations:** Synthetic patients and matching protocols; screening support only. An investigator decides formal eligibility. No production authentication, actual EHR integration, real patient contact, real appointments, HIPAA-compliance determination, or validated automatic protocol interpretation. Existing federated matching companies exist; the project explores the combination of reassessment, clinic control, data reuse and patient choice.

**Before submitting:** Add your team names, repository URL and video link. Use screenshots from `docs/screenshots/` and the local backup in `artifacts/`. Confirm event-day rules, including any prebuilt-code policy. This file does not publish or submit anything.
