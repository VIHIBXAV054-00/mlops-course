.PHONY: up down down-v logs ps sync dvc-init next-batch build-data dvc-add dvc-push \
        dvc-pull dvc-status dvc-roundtrip dvc-timetravel repro dag metrics \
        link runs-for-data register promote trace all test test-fast

# DVC reads the Silo keys from AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY, so
# every dvc call gets them from the Silo block in .env. No key goes into
# .dvc/config. DVC_PAGER=cat stops `dvc dag` from opening a pager.
DOTENV = set -a && . ./.env && set +a
DVC    = $(DOTENV) && AWS_ACCESS_KEY_ID="$$S3_ACCESS_KEY" \
                      AWS_SECRET_ACCESS_KEY="$$S3_SECRET_KEY" \
                      DVC_PAGER=cat uv run dvc

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

## Exercise 1 — initialise DVC and point the remote at Silo
dvc-init:
	$(DVC) init --subdir
	$(DVC) config core.autostage true
	$(DVC) config core.analytics false
	$(DVC) config core.check_update false
	$(DOTENV) && uv run dvc remote add -d $$DVC_REMOTE_NAME s3://$$DVC_BUCKET/$$DVC_REMOTE_PATH
	$(DOTENV) && uv run dvc remote modify $$DVC_REMOTE_NAME endpointurl http://127.0.0.1:$$S3_API_PORT
	@echo
	@echo "--- .dvc/config (note: NO credentials in here) ---"
	@cat .dvc/config

## Exercises 2 and 4 — the next batch arrives: data/incoming/ -> data/raw/
next-batch:
	uv run python src/main.py next-batch

## Exercises 2 and 4 — merge the batches in data/raw/ into data/measurements.csv
build-data:
	uv run python src/main.py build-data

## Exercises 2 and 4 — track the dataset with DVC
dvc-add:
	$(DVC) add data/measurements.csv
	@echo
	@echo "--- data/measurements.csv.dvc ---"
	@cat data/measurements.csv.dvc
	@echo "--- data/.gitignore (DVC wrote this, in data/) ---"
	@cat data/.gitignore

## Exercises 2 and 4 — upload the bytes to Silo
dvc-push:
	$(DVC) push

## Pull the bytes back from Silo
dvc-pull:
	$(DVC) pull

## Compare workspace / cache / remote
dvc-status:
	$(DVC) status
	$(DVC) status --cloud

## Exercise 3, in one target: empty cache, checkout fails, pull restores
dvc-roundtrip:
	rm -f data/measurements.csv
	rm -rf .dvc/cache
	@echo "--- dvc checkout with an empty cache (expected to FAIL) ---"
	-$(DVC) checkout data/measurements.csv
	@echo "--- dvc pull (fetches from Silo) ---"
	$(DVC) pull data/measurements.csv
	uv run python src/main.py verify-data

## Exercise 4, in one target: back to version 1 and forward again.
## Usage: make dvc-timetravel REV=<commit of version 1>
dvc-timetravel:
	@test -n "$(REV)" || { echo "Usage: make dvc-timetravel REV=<commit of version 1>"; \
	  echo "Find it with: git log --oneline -- data/measurements.csv.dvc"; exit 1; }
	git checkout $(REV) -- data/measurements.csv.dvc
	$(DVC) checkout data/measurements.csv
	uv run python src/main.py verify-data
	git checkout HEAD -- data/measurements.csv.dvc
	$(DVC) checkout data/measurements.csv
	uv run python src/main.py verify-data

## Exercise 5 — run the declared pipeline (only stale stages re-run)
repro:
	$(DVC) repro

## Exercise 5 — show the pipeline graph
dag:
	$(DVC) dag
	@echo "--- as mermaid ---"
	$(DVC) dag --mermaid

## Exercise 5 — show recorded metrics
metrics:
	$(DVC) metrics show

## Exercise 6 — force a new training run, then its evaluation.
## -s forces only the named stage; `-f train` alone would re-run `prepare` too.
link:
	$(DVC) repro -f -s train
	$(DVC) repro -f -s evaluate
	$(DVC) repro

## Exercise 6 — find every MLflow run trained on the current data version
runs-for-data:
	uv run python src/main.py runs-for-data

## Register the winning model (Week 3 mechanics)
register:
	uv run python src/main.py register

## Promote it with an alias (Week 3 mechanics)
promote:
	uv run python src/main.py promote

## Exercise 6 — walk the chain: alias -> version -> run -> data version -> bytes
trace:
	uv run python src/main.py trace

## Version 2, the pipeline and the chain in one go, after `make dvc-init`
all:
	uv run python src/main.py build-data
	$(DVC) add data/measurements.csv
	$(DVC) push
	$(DVC) repro
	uv run python src/main.py register
	uv run python src/main.py promote
	uv run python src/main.py trace

## Run every test (live/dvc tests auto-skip when their prerequisite is absent)
test:
	uv run pytest tests/ -v

## Run only the tests that need neither the stack nor a DVC repo
test-fast:
	uv run pytest tests/ -v -m "not live and not dvc"
