.PHONY: up down down-v logs ps sync build-data verify-data dvc-push dvc-pull dvc-status \
        validate validate-broken validate-model-input repro dag metrics gate-fail \
        predict predict-bad link runs-for-data register promote trace test test-fast

# DVC reads the Silo keys from AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY, so
# every dvc call gets them from the Silo block in .env. No key goes into
# .dvc/config. DVC_PAGER=cat stops `dvc dag` from opening a pager.
DOTENV = set -a && . ./.env && set +a
DVC    = $(DOTENV) && AWS_ACCESS_KEY_ID="$$S3_ACCESS_KEY" \
                      AWS_SECRET_ACCESS_KEY="$$S3_SECRET_KEY" \
                      DVC_PAGER=cat uv run dvc
TRAIN_MD5 = uv run python -c "import hashlib; \
	print(hashlib.md5(open('data/processed/train.csv', 'rb').read()).hexdigest())"

## Bring up all four services and wait for healthchecks
up:
	docker compose up -d --wait

## Stop services (data persists in named volumes)
down:
	docker compose down

## Stop services AND wipe all volumes (fresh start)
down-v:
	docker compose down -v

## Stream logs from all services
logs:
	docker compose logs -f

## Show status of all services
ps:
	docker compose ps

## Install Python dependencies
sync:
	uv sync --all-groups

## Setup — merge the batches in data/raw/ into data/measurements.csv
build-data:
	uv run python src/main.py build-data

## Compare the data on disk with its DVC pointer
verify-data:
	uv run python src/main.py verify-data

## Upload the data to Silo
dvc-push:
	$(DVC) push

## Download the data from Silo
dvc-pull:
	$(DVC) pull data/measurements.csv

## Compare workspace / cache / remote
dvc-status:
	$(DVC) status
	$(DVC) status --cloud

## Exercise 1 — check data/measurements.csv against RawMeasurements (writes no report)
validate:
	uv run python src/main.py check-file data/measurements.csv

## Exercise 2 — check the broken batch against RawMeasurements
validate-broken:
	uv run python src/main.py check-file data/quality/broken_batch.csv

## Exercise 3 — check the data against ModelInput, before and after to_nullable
validate-model-input:
	uv run python src/main.py model-input

## Exercises 4 and 5 — run the declared pipeline (only stale stages re-run)
repro:
	$(DVC) repro

## Exercise 4 — show the pipeline graph
dag:
	$(DVC) dag
	@echo "--- as mermaid ---"
	$(DVC) dag --mermaid

## Exercise 5 — show recorded metrics
metrics:
	$(DVC) metrics show

## Exercise 4 — plant an impossible age (250) in the tracked data, run the
## pipeline, then put the data back and run it again
gate-fail:
	@echo "--- md5 of data/processed/train.csv before ---"
	@$(TRAIN_MD5)
	@cp data/measurements.csv .gate-fail.bak
	@uv run python -c "import pandas as pd; \
		f = pd.read_csv('data/measurements.csv'); f.loc[1, 'age'] = 250; \
		f.to_csv('data/measurements.csv', index=False, lineterminator='\n')"
	@echo "--- planted age = 250 in row 1; dvc repro ---"
	-$(DVC) repro
	@echo "--- md5 of data/processed/train.csv after ---"
	@$(TRAIN_MD5)
	@echo "--- putting the data back; dvc repro ---"
	@mv .gate-fail.bak data/measurements.csv
	$(DVC) repro

## Exercise 6 — one legal request
predict:
	uv run python src/main.py predict --payload example

## Exercise 6 — three bad requests, one after another
predict-bad:
	@for case in illegal swapped incomplete; do \
		echo "=================== $$case ==================="; \
		uv run python src/main.py predict --payload $$case; \
	done

## Exercise 6 — force a new training run, then its evaluation.
## -s forces only the named stage; `-f train` alone would re-run `prepare` too.
link:
	$(DVC) repro -f -s train
	$(DVC) repro -f -s evaluate
	$(DVC) repro

## Find every MLflow run trained on the current data version
runs-for-data:
	uv run python src/main.py runs-for-data

## Register the latest run's model (Week 3 mechanics)
register:
	uv run python src/main.py register

## Promote it with an alias (Week 3 mechanics)
promote:
	uv run python src/main.py promote

## Exercise 6 — walk the chain: alias -> run -> data version -> validation verdict
trace:
	uv run python src/main.py trace

## Run every test (the live tests skip when the stack is down)
test:
	uv run pytest tests/ -v

## Run only the tests that need neither the stack nor a DVC repo
test-fast:
	uv run pytest tests/ -v -m "not live and not dvc"
