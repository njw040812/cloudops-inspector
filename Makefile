PYTHON ?= python3
VENV ?= .venv

.PHONY: install test inspect history serve docker-build clean

install:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install -r requirements-dev.txt

test:
	$(VENV)/bin/python -m pytest

inspect:
	$(VENV)/bin/python -m cloudops_inspector inspect \
		--inventory examples/inventory.local.yml \
		--rules rules/default.yml \
		--db data/inspector.db \
		--output reports

history:
	$(VENV)/bin/python -m cloudops_inspector history --db data/inspector.db

serve:
	$(VENV)/bin/python -m cloudops_inspector serve --db data/inspector.db --port 8000

docker-build:
	docker build -t cloudops-inspector .

clean:
	rm -rf .pytest_cache data reports
