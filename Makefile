.PHONY: install test phase1-demo

PYTHONPATH ?= .

install:
	pip install -r requirements.txt

test:
	PYTHONPATH=$(PYTHONPATH) pytest tests/ -v

phase1-demo:
	PYTHONPATH=$(PYTHONPATH) python scripts/phase1_demo.py
