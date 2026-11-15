PYTHON ?= python
.PHONY: setup seed demo reset test
setup:
	$(PYTHON) scripts/setup.py
seed:
	.venv/Scripts/python scripts/generate_synthetic.py
demo:
	.venv/Scripts/python scripts/run_demo.py
reset:
	.venv/Scripts/python scripts/reset_demo.py
test:
	.venv/Scripts/python -m pytest -q
