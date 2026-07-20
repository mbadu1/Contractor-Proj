.PHONY: install test phase1-demo phase2-demo

PYTHONPATH ?= .

install:
	pip install -r requirements.txt

test:
	PYTHONPATH=$(PYTHONPATH) pytest tests/ -v

phase1-demo:
	PYTHONPATH=$(PYTHONPATH) python scripts/phase1_demo.py

phase2-demo:
	PYTHONPATH=$(PYTHONPATH) python scripts/phase2_demo.py
