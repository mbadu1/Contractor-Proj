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

phase3-demo:
	PYTHONPATH=$(PYTHONPATH) python scripts/phase3_demo.py

phase3-quick:
	PYTHONPATH=$(PYTHONPATH) python scripts/phase3_demo.py --quick

phase4-demo:
	PYTHONPATH=$(PYTHONPATH) python scripts/phase4_demo.py --quick

phase4-full:
	PYTHONPATH=$(PYTHONPATH) python scripts/phase4_demo.py
