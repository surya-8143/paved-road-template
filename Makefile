PYTHON ?= python3
IMAGE ?= paved-road-service:local

.PHONY: install test lint format image smoke
install:
	$(PYTHON) -m pip install --require-hashes --only-binary=:all: -r requirements-dev.txt
lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .
format:
	$(PYTHON) -m ruff format .
test:
	$(PYTHON) -m pytest --cov=app --cov-report=term-missing -q
image:
	docker build -t $(IMAGE) .
smoke: image
	bash scripts/smoke_container.sh $(IMAGE)

.PHONY: package verify-package
package:
	$(PYTHON) -m scripts.package_lambda
verify-package: package
	bash scripts/smoke_lambda.sh
