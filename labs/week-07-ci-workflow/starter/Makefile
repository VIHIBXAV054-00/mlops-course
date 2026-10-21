.PHONY: up down down-v logs ps sync verify-data dvc-init data-v1 data-v2 dvc-add dvc-push \
        dvc-pull dvc-status dvc-roundtrip repro dag metrics link \
        runs-for-data register promote promote-champion trace all test test-fast \
        validate validate-broken validate-model-input predict predict-bad \
        data-gate-fail slices gate fairness baseline baseline-sync gate-fail \
        ratchet lint ensure-env ensure-data ci ci-local ct-local ci-fail \
        gate-summary ci-explain install-ci uninstall-ci \
        test-unit test-data test-eval test-integration

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

## Print the slice table (n and positives per group)
slices:
	uv run python src/main.py slices

## The go/no-go decision; exits non-zero on a NO-GO and always writes the report
gate:
	uv run python src/main.py gate

## Selection rate, TPR and FPR per group, and the three gaps
fairness:
	uv run python src/main.py fairness

## Print the recorded baseline
baseline:
	uv run python src/main.py baseline

## Record the current champion as the baseline
baseline-sync:
	uv run python src/main.py baseline-sync

## Over-regularise the model (train.C 0.005), run the pipeline, then restore params.yaml.
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

## Train a random forest, make it champion and sync the baseline;
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

## Lint src and tests with the pinned ruff and the rules in pyproject.toml
lint:
	uv run ruff check src tests

## Copy .env.example to .env when there is none, as on a fresh runner
ensure-env:
	@test -f .env || { cp .env.example .env; echo "No .env found: copied .env.example."; }

## Stop with a hint when the DVC-tracked dataset is missing, as on a fresh runner
ensure-data:
	@test -f data/measurements.csv || { \
	  echo "data/measurements.csv is missing. Build it from the committed batches:"; \
	  echo "    make data-v2"; \
	  exit 1; }

## The one entry point: lint, tests, pipeline and gate. Both workflows call it
# TODO(student) Exercise 2: list the targets `ci` runs, in order, after the two
# ensure-* targets. Reuse targets that already exist above; do not copy their recipes.
# `make` stops at the first target that fails.
ci: ensure-env ensure-data
	@echo "make ci is not written yet (Exercise 2)."
	@exit 1

## The steps of ci.yml on your machine, in the runner's order
ci-local: ensure-env ensure-data
	@echo "==> lint";     $(MAKE) --no-print-directory lint
	@echo "==> unit";     $(MAKE) --no-print-directory test-unit
	@echo "==> data";     $(MAKE) --no-print-directory test-data
	@echo "==> eval";     $(MAKE) --no-print-directory test-eval
	@echo "==> pipeline"; $(MAKE) --no-print-directory repro
	@echo "==> gate";     $(MAKE) --no-print-directory gate

## The steps of ct.yml: retrain and gate, with no code change
ct-local: ensure-env ensure-data
	$(MAKE) --no-print-directory repro
	$(MAKE) --no-print-directory gate

## Plant train.C 0.005, run `make ci`, and restore params.yaml; `make ci` must fail
ci-fail:
	@cp params.yaml .params.yaml.ci-bak
	@sed -i.tmp 's/^  C: 1.0$$/  C: 0.005/' params.yaml && rm -f params.yaml.tmp
	@grep -q '^  C: 0.005$$' params.yaml || { \
	  echo "Could not plant train.C: 0.005. Check the indentation in params.yaml."; \
	  mv .params.yaml.ci-bak params.yaml; exit 1; }
	@echo "Planted train.C: 0.005. Running make ci..."
	@set +e; $(MAKE) --no-print-directory ci; rc=$$?; set -e; \
	  echo; echo "make ci exit code: $$rc"; \
	  mv .params.yaml.ci-bak params.yaml; \
	  echo "params.yaml restored. Run make repro to return to a GO."; \
	  test "$$rc" -ne 0 || { echo; \
	    echo "make ci passed with train.C: 0.005, so it does not run the gate."; \
	    exit 1; }

## The recorded gate verdict as Markdown, for the job summary
gate-summary:
	@uv run python src/main.py gate-summary

## The workflows in this lab and at the repository root, with their action pins
ci-explain:
	@uv run python src/main.py ci-explain

## Copy the lab's workflows to .github/workflows at the repository root, where GitHub runs them
install-ci:
	@root=$$(git rev-parse --show-toplevel) && mkdir -p "$$root/.github/workflows" && \
	  for f in .github/workflows/*.yml; do \
	    cp "$$f" "$$root/.github/workflows/week07-$$(basename $$f)"; \
	    echo "installed -> .github/workflows/week07-$$(basename $$f)"; \
	  done
	@echo "Commit and push to run them. make uninstall-ci removes them."

## Remove the installed copies from the repository root
uninstall-ci:
	@root=$$(git rev-parse --show-toplevel) && \
	  rm -f "$$root"/.github/workflows/week07-*.yml && echo "removed week07-*.yml"

## One test layer each; data and eval leave out the tests that need the stack or DVC
test-unit:
	uv run pytest tests/ -q -m "unit"

test-data:
	uv run pytest tests/ -q -m "data and not live and not dvc"

test-eval:
	uv run pytest tests/ -q -m "eval and not live and not dvc"

## Needs the stack, so CI does not run it
test-integration:
	uv run pytest tests/ -q -m "integration"
