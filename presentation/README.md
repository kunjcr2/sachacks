# ReMatch judging slides

10-frame Beamer deck for a ~5-minute talk with the live app beside the slides.

**PDF:** [`presentation_main.pdf`](presentation_main.pdf)

## Compile

Needs **XeLaTeX** or **LuaLaTeX** (theme uses `fontspec`). Run twice for the frame count:

```bash
cd presentation
# If packages are missing (TeX Live Basic), install into your user tree:
# tlmgr init-usertree
# tlmgr --usermode install tcolorbox tikzfill spath3 beamer appendixnumberbeamer booktabs pgfplots pgf xcolor environ trimspaces pdfcol enumitem
xelatex presentation_main.tex
xelatex presentation_main.tex
```

**Overleaf:** upload `presentation_main.tex` + `beamerthemeterminal.sty`, set compiler to XeLaTeX.

Theme notes: [THEME.md](THEME.md).

## Slide map

| # | Frame | Role |
| --- | --- | --- |
| 1 | Title | ReMatch · Kunj Shah, Devarsh Shroff |
| 2 | Problem | Recruitment gap + PCP burden |
| 3 | Pitch | Connect → match → doctor when needed → auth |
| 4 | Platform | Patient / usual doctor / research team |
| 5–8 | Live demo cues | Happening / why helpful / resistance removed |
| 9 | Flow & safeguards | Architecture aligned with `docs/info_flow.md` |
| 10 | Questions | Closing screen |
