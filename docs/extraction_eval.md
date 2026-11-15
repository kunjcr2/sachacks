# Source-grounded generation and validation

The live path uses the configured server-side OPENAI_MODEL with the OpenAI Responses API and Structured Outputs. It sends only allow-listed public registry or explicitly synthetic study sources, never patient data. It extracts criteria and five brief claims, then performs a separate model consistency review. That automated review is not independent clinical certification.

Deterministic checks reject invented quotations/locations, duplicate rules, unregistered fields, unsupported units, invalid bounds/operators, polarity changes, inferred rule modifiers, compound/temporal logic and incomplete clause coverage. Unknown clauses are preserved as unmapped and block publication. The deliberately narrow executable grammar handles simple atomic numeric and boolean statements; complex real protocols will remain blocked rather than silently simplified. Registry demographic restrictions outside the narrative are included in coverage.

Briefs have exactly these headings: Purpose; What participation involves; Main risks and uncertainties; Possible benefits; Costs and compensation. Each factual line is an exact source quotation with location. Missing information is labeled "Not provided in the available study information." Individual benefit is never guaranteed. Research importance remains separate. Risk support does not come from trial phase, observational design, payment or general model knowledge. Missing/conflicting/unsupported low-risk evidence routes UNKNOWN to the doctor.

Successful validated model output is cached by source hash, model, prompt version and schema version. Reuse revalidates source claims. Source hashes include recruitment status and supplied documents; changes suspend existing listings and invalidate pending actions before regeneration. Only validated material can publish. Closed studies are never actionable.

The offline examples are declared synthetic fixtures with deterministic source-grounded specifications, separately labeled offline_synthetic_fixture. They are not represented as live model output or clinician-verified protocols. Live calls use live_model; successful model-cache reuse uses validated_model_cache. API failures report failure and retain valid cached material.

Tests exercise missing clauses, altered thresholds/operators/fields/units/polarity, false quotes, unsupported logic, invalid locations, failed model review, explicit missing facts, source/version cache keys, public-cache provenance, patient-data prompt exclusion and conservative risk routing. Formal semantic/clinical validation across real protocols remains future work.

Implementation verification on November 15, 2026: offline fixtures and the complete simulated workflow pass. A real configured-key generation attempt reached OpenAI but returned AuthenticationError. No live generation success is claimed; update the key locally to repeat the live check.
