.PHONY: up down down-v logs ps sync verify-data dvc-init data-v1 data-v2 dvc-add dvc-push \
        dvc-pull dvc-status dvc-roundtrip repro dag metrics link \
        runs-for-data register promote promote-champion trace all test test-fast \
        validate validate-broken validate-model-input predict predict-bad \
        data-gate-fail slices gate fairness baseline baseline-sync gate-fail \
        ratchet

# Every recipe that calls dvc sources .env and passes the Silo keys on as the
# AWS_* names that DVC reads, so no key is written into .dvc/config.
# DVC_PAGER=cat stops `dvc dag` from opening a pager.
DOTENV = set -a && . ./.env && set +a
DVC    = $(DOTENV) && AWS_ACCESS_KEY_ID="$$S3_ACCESS_KEY" \
                      AWS_SECRET_ACCESS_KEY="$$S3_SECRET_KEY" \
                      DVC_PAGER=cat uv run dvc

## Start all four services and wait for the healthchecks
up:
	docker compose up -d --wait

## Stop the services (data stays in the named volumes)
down:
	docker compose down

## Stop the services and delete the volumes (fresh start)
down-v:
	docker compose down -v

## Follow the logs of all services
logs:
	docker compose logs -f

## Show the status of all services
ps:
	docker compose ps

## Install the Python dependencies
sync:
	uv sync --all-groups

## Setup: initialise DVC and point the remote at Silo
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

## Setup: build dataset version 1 (the baseline batch only)
data-v1:
	uv run python src/main.py build-data --version 1

## Setup: build dataset version 2 (baseline batch and new arrival)
data-v2:
	uv run python src/main.py build-data --version 2

## Setup: track the dataset with DVC
dvc-add:
	$(DVC) add data/measurements.csv
	@echo
	@echo "--- data/measurements.csv.dvc ---"
	@cat data/measurements.csv.dvc
	@echo "--- data/.gitignore (DVC wrote this, in data/) ---"
	@cat data/.gitignore

## Compare the data on disk with its DVC pointer
verify-data:
	uv run python src/main.py verify-data

## Setup: upload the data to Silo
dvc-push:
	$(DVC) push

## Download the data from Silo
dvc-pull:
	$(DVC) pull

## Compare workspace, cache and remote
dvc-status:
	$(DVC) status
	$(DVC) status --cloud

## Delete the data and the cache, then restore the data from Silo
dvc-roundtrip:
	rm -f data/measurements.csv
	rm -rf .dvc/cache
	@echo "--- dvc checkout with an empty cache (expected to FAIL) ---"
	-$(DVC) checkout
	@echo "--- dvc pull (fetches from Silo) ---"
	$(DVC) pull
	uv run python src/main.py verify-data

## Check the data against its contract and write the verdict; exits non-zero on failure
validate:
	uv run python src/main.py validate

## Check the corrupted batch against the contract; exits 0, read the report
validate-broken:
	uv run python src/main.py check-file

## Check the training contract, failing then passing
validate-model-input:
	uv run python src/main.py model-input

## Run the declared pipeline (only stale stages re-run); it ends at `gate`
repro:
	$(DVC) repro

## Exercises 1 and 2: print the slice table (n and positives per group)
slices:
	uv run python src/main.py slices

## Exercises 3 and 4: the go/no-go decision; exits non-zero on a NO-GO and always writes the report
gate:
	uv run python src/main.py gate

## Exercise 5: selection rate, TPR and FPR per group, and the three gaps
fairness:
	uv run python src/main.py fairness

## Exercise 6: print the recorded baseline
baseline:
	uv run python src/main.py baseline

## Exercise 6: record the current champion as the baseline
baseline-sync:
	uv run python src/main.py baseline-sync

## Exercise 4: over-regularise the model (train.C 0.005), run the pipeline, then restore params.yaml.
## `dvc repro` must stop at `gate`, `register` and `promote` must refuse, and models/model.pkl must stay
gate-fail:
	@cp params.yaml .gate-fail.bak
	@echo "--- over-regularising the model: train.C 1.0 -> 0.005 ---"
	@uv run python -c "import pathlib; p=pathlib.Path('params.yaml'); p.write_text(p.read_text().replace('  C: 1.0', '  C: 0.005'))"
	@echo
	@echo "--- dvc repro (expected to FAIL at the gate stage) ---"
	-$(DVC) repro
	@echo
	@echo "--- the model must still be on disk ---"
	@ls -l models/model.pkl
	@echo
	@echo "--- register must REFUSE (expected exit 1) ---"
	-uv run python src/main.py register
	@echo "--- promote must REFUSE (expected exit 1) ---"
	-uv run python src/main.py promote
	@echo
	@echo "--- restoring params.yaml ---"
	@mv .gate-fail.bak params.yaml
	$(DVC) repro

## Exercise 6: train a random forest, make it champion and sync the baseline;
## the logistic regression then fails the gate. The target restores params.yaml and
## metrics/baseline.json at the end; the `champion` alias stays on the random forest
ratchet:
	@cp params.yaml .gate-fail.bak
	@cp metrics/baseline.json .baseline.bak
	@echo "=================== 1. a better model ==================="
	@uv run python -c "import pathlib; p=pathlib.Path('params.yaml'); p.write_text(p.read_text().replace('  family: logreg', '  family: rf'))"
	$(DVC) repro
	uv run python src/main.py gate
	@echo "=================== 2. crown it ==================="
	uv run python src/main.py register
	uv run python src/main.py promote --champion
	uv run python src/main.py baseline-sync
	@echo "=================== 3. the old model, against the new bar ==================="
	@mv .gate-fail.bak params.yaml
	-$(DVC) repro
	@echo
	@echo "The logistic regression did not get worse. The bar got higher."
	@echo
	@echo "=================== 4. put the bar back ==================="
	@mv .baseline.bak metrics/baseline.json
	$(DVC) repro

## Plant an impossible age (250) in the tracked data and run the pipeline;
## it must stop at `validate`. Then restore the data
data-gate-fail:
	@echo "--- before: processed data timestamps ---"
	@ls -l data/processed/ 2>/dev/null || echo "  (no processed data yet)"
	@echo
	@echo "--- planting an impossible age (250) in row 1 ---"
	@cp data/measurements.csv .gate-fail.bak
	@uv run python -c "import pandas as pd; f=pd.read_csv('data/measurements.csv'); f.loc[0,'age']=250; f.to_csv('data/measurements.csv', index=False, lineterminator='\n')"
	@echo
	@echo "--- dvc repro (expected to FAIL at the validate stage) ---"
	-$(DVC) repro
	@echo
	@echo "--- after: processed data must be UNCHANGED ---"
	@ls -l data/processed/ 2>/dev/null || echo "  (no processed data)"
	@echo
	@echo "--- restoring the data ---"
	@mv .gate-fail.bak data/measurements.csv
	$(DVC) repro

## Show the pipeline graph
dag:
	$(DVC) dag
	@echo "--- as mermaid ---"
	$(DVC) dag --mermaid

## Show the recorded metrics
metrics:
	$(DVC) metrics show

## Validate a request, then predict (--payload example, illegal, swapped or incomplete)
predict:
	uv run python src/main.py predict --payload example

## Send the three bad requests, one after another
predict-bad:
	@for case in illegal swapped incomplete; do \
		echo "=================== $$case ==================="; \
		uv run python src/main.py predict --payload $$case; \
	done

## Force a new training run, then its evaluation.
## -s forces only the named stage; `-f train` alone would re-run `prepare` too
link:
	$(DVC) repro -f -s train
	$(DVC) repro -f -s evaluate
	$(DVC) repro

## Find every MLflow run trained on the current data version
runs-for-data:
	uv run python src/main.py runs-for-data

## Register the model; refuses unless reports/gate.json records a GO
register:
	uv run python src/main.py register

## Move the `staging` alias; refuses unless the gate records a GO
promote:
	uv run python src/main.py promote

## Move `staging` and `champion`; this raises the bar for the baseline
promote-champion:
	uv run python src/main.py promote --champion

## Walk the chain: alias -> run -> data -> validation -> gate verdict
trace:
	uv run python src/main.py trace

## Run the whole week, assuming DVC is initialised
all:
	uv run python src/main.py build-data --version 2
	$(DVC) add data/measurements.csv
	$(DVC) push
	$(DVC) repro
	uv run python src/main.py slices
	uv run python src/main.py fairness
	uv run python src/main.py gate
	uv run python src/main.py register
	uv run python src/main.py promote --champion
	uv run python src/main.py baseline-sync
	uv run python src/main.py trace

## Run every test (the live and dvc tests skip when their prerequisite is missing)
test:
	uv run pytest tests/ -v

## Run only the tests that need neither the stack nor a DVC repo
test-fast:
	uv run pytest tests/ -v -m "not live and not dvc"
