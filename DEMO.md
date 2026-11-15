# Run the ReMatch demo

```powershell
python scripts/setup.py
.\.venv\Scripts\python.exe scripts/run_demo.py --reset
```

One URL: **http://localhost:8000**. The same FastAPI process serves the UI and API. Stop the old launcher first; reset refuses to proceed while any previous demo port is active. `--reset` deliberately reseeds only the new central schema. Omitting it preserves central state. Ctrl+C closes the owned backend and UI processes.

1. In **Study team**, use team-1. Fetch/cache SYN-LOW and choose **Offline synthetic fixture**, then validate/list. The existing seeded listing is reused idempotently. Show the **Demo payment — no charge** receipt, source quotations, validation metadata and five-line brief. Optional: choose live public-text LLM generation with the local server key. A failed API call is a failure, never a fixture disguised as live output.
2. In **My studies**, choose patient-1 (Alex Demo), or create a new fake profile without a clinic invitation. Point out the separate earned demo time credit. Declining screening remains a valid choice.
3. Allow research matching and simulated record access separately. Open **Connect my records — simulated Epic**, confirm the fake authorization, and import. No real credentials are collected. Retained encrypted records support future screening without another import.
4. **Everyday Balance**, the supported low-risk fixture, appears directly. Request an introduction to preview the exact packet. The doctor has zero tasks for this listing, regardless of benefit or compensation.
5. The higher-risk **Treatment Questions** and unknown-risk **Health Conversations** initially show a neutral doctor-review status. In **Doctor review**, cases are grouped under the assigned patient. Complete the Treatment Questions discussion. The doctor neither declares eligibility nor authorizes disclosure.
6. Return to the same patient. Preview the higher-risk study introduction, inspect the named PI/site, name/contact, relevant screening summary and record/study versions, and explicitly confirm this one disclosure. Patient permission is required even after discussion.
7. In **Study team**, team-1 sees the authorized packet. Team-2 sees none. Acknowledge, invite to formal screening, then explicitly record a simulated enrollment outcome if desired. An introduction or acknowledgment alone is never enrollment, and no doctor payout exists.
8. Return to **My studies**. Withdraw an introduction, stop research matching, or delete stored records. Show the in-app retraction and retained earned time credit. Disconnecting records is a separate action that stops future imports.
9. Optional reassessment: while both permissions are active, import the changed synthetic follow-up under **My data and demo controls**. HbA1c changes from 11.2% to 9.1%, creating a ReNew T2D opportunity. Advancing the persisted demo clock 91 days makes that lab stale; elapsed time alone does not improve a result.

Patient-2 has no assigned doctor: supported low-risk opportunities still work; higher/unknown-risk cases remain pending with instructions to arrange review. All fixture risk labels are deliberately declared synthetic routing designations.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/run_demo.py --reset --check --no-browser
# With the replacement backend running:
.\.venv\Scripts\python.exe scripts/check_demo.py --repeat 2
```

The launcher check verifies the React build and one backend, then stops it. The browser-session API walkthrough creates a new synthetic profile per run and checks onboarding, import, both routing paths, exact disclosure permissions, recipient isolation, withdrawal and deletion. It does not erase existing profiles. Backend tests cover role credentials, encrypted persistence and authenticated ownership, source fidelity, failed model review, unknown-risk fallback, stale/missing facts, version invalidation, repeated delivery, payments and reassessment.

Model tests use an explicit fake client; offline success, validated model-cache reuse and live success are separate execution labels. A real live check requires working credentials/network and may incur a small model API charge. The listing receipt itself never charges money.
