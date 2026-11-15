# ReMatch — setup and judges' demo

**On this computer, everything is installed.** From PowerShell in this folder:

```powershell
.\.venv\Scripts\python.exe scripts/run_demo.py --reset
```

Keep that terminal open. Open [Clinic](http://localhost:8501), [Sponsor](http://localhost:8502), and [Patient](http://localhost:8503). No API key or internet is needed for the core demo. All patients and matching protocols are fictional.

**Fresh computer:** install Python 3.11+ (standard python.org build) or [uv](https://docs.astral.sh/uv/getting-started/installation/). Run `python scripts/setup.py` (or `uv sync --locked --python 3.12`), then the command above. On macOS/Linux use `.venv/bin/python`.

## The 4-minute walkthrough

1. **Clinic → Overview:** select Sunrise Family Health. “Patients get screened out once, but their records change. ReMatch takes another look locally.”
2. **Clinic → Review Queue:** default case is **PX-82914 / SYN-0001**. Show HbA1c **11.2%**, the **7.5–10%** requirement, and the watch. Matching uses Python rules, never an LLM.
3. **Sponsor → Network feasibility:** show the two clinics' aggregate counts. No names or patient rows.
4. **Clinic:** click **+90 days**. Old facts become stale; time alone does not improve a result. Click **Simulate lab feed**. This supplies HbA1c **9.1%**, eGFR **68**, refreshed BMI and pregnancy assessment. Show the reassessment alert, before/after table and reuse labels in **Review Queue**.
5. Click **Approve & send de-identified packet**. **Sponsor → Network Inspector:** show the hub's ciphertext. **Candidate inbox:** show the pseudonym, age band and evidence; click **Confirm for clinic follow-up**.
6. **Clinic:** click **Sync trials now**, then **Outreach & participation → Release opportunity to patient**.
7. **Patient:** sign in as **PX-82914**, click **Refresh**, then **I'm interested**. **Clinic:** Refresh → **Arrange screening referral**. Return to **Patient → My participation** to show the next step.
8. Optionally click **Pause or withdraw from research**. Refresh the Sponsor inbox to show retraction. “Patients choose; the clinic controls outreach; investigators decide formal eligibility.”

## Reset, fallback, and testing

- **Repeat the hero demo:** Clinic sidebar → **Reset selected clinic → Reset clinic to day zero**, then **Sync trials now**. Previously sent packets are retracted. This preserves other clinics and protocol amendments.
- **Full clean reset:** Ctrl+C in the terminal, then rerun the launch command with `--reset`. This resets both clinics, protocols, aggregates and referrals.
- **If a service stops:** Ctrl+C, restart; check `runtime/logs/`. If a port is already in use, close the earlier launcher. Backend API pages require local credentials; use the three app links above.
- Wait for **All six processes are healthy** before opening the apps. The launcher prints each service as it starts. An **interrupt** message means the terminal or OS interrupted the launcher; a service failure instead shows its exit code and log excerpt.
- **Backup:** play `artifacts/rematch-backup.webm` in Edge/Chrome. Screenshots are in `docs/screenshots/`.
- **Tests:** `.\.venv\Scripts\python.exe -m pytest -q`. With the demo running, `scripts/check_demo.py --repeat 3` checks every app page and the full UI flow; it resets fictional Clinic A.
- **Extra demo:** Sponsor → **Protocol amendment**, verify and publish HbA1c max **11.5%**, then sync Clinic A at day zero. The protocol change itself reveals the hero. Use a full reset before the usual lab-update walkthrough.

Optional OpenAI extraction is separate from the reliable demo: copy `.env.example` to `.env`, set `OPENAI_API_KEY` and `OPENAI_MODEL` to a Structured Outputs model supporting `temperature=0`, restart, then use **Sponsor → Trials & publication → Extract draft rules**. Only public trial text is sent. Drafts require human review and are never automatically published. No other paid API keys are needed.
