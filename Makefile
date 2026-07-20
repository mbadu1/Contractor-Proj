.PHONY: install test phase1-demo phase2-demo phase3-demo phase3-quick phase4-demo phase4-full phase5-demo phase6-demo phase7-demo api dashboard demo scheduler docker-up docker-down

PYTHONPATH ?= .

install:
	pip install -r requirements.txt
	cd dashboard && npm install

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

phase5-demo:
	PYTHONPATH=$(PYTHONPATH) python scripts/phase5_demo.py --quick

phase6-demo:
	PYTHONPATH=$(PYTHONPATH) python scripts/phase6_demo.py

phase7-demo:
	@echo "Build dashboard + open with API. Prefer: make demo"
	cd dashboard && npm run build

api:
	PYTHONPATH=$(PYTHONPATH) uvicorn api.main:app --host 0.0.0.0 --port 8000

dashboard:
	cd dashboard && npm run dev -- -H 0.0.0.0 -p 3000

demo:
	chmod +x scripts/demo.sh
	./scripts/demo.sh

scheduler:
	PYTHONPATH=$(PYTHONPATH) python -m orchestration.scheduler

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down
