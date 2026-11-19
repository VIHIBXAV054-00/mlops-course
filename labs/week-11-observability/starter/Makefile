.PHONY: up down down-v logs ps sync dvc-init data-v1 data-v2 dvc-add dvc-push \
        dvc-pull dvc-status dvc-roundtrip repro dag metrics link \
        runs-for-data register promote promote-champion trace all test test-fast \
        validate validate-broken validate-model-input predict predict-bad \
        data-gate-fail slices gate fairness baseline baseline-sync gate-fail \
        ratchet lint fmt-check ci ci-local ct-local ci-fail ci-explain \
        install-ci uninstall-ci test-unit test-data test-eval test-integration \
        ensure-env gate-summary ensure-data flow flow-dvc flow-retry \
        serve-mlflow serve-api bench image run-image kind-up kind-down \
        k8s-deploy k8s-rollout k8s-status \
        flow-params flow-fail serve prefect-ui test-flows \
        kserve-install kserve-status kserve-uninstall model-publish \
        model-publish-variant store-list isvc-deploy isvc-canary isvc-status \
        isvc-url isvc-health isvc-down split-measure loadtest smoke smoke-local \
        _job promote-canary rollback rollback-reapply test-rollout \
        metrics-show api-up api-down api-logs traffic traffic-errors promql \
        logs-json cardinality grafana prometheus-ui dashboard-check slo-budget \
        alerts-check alerts-test alerts-test-fail alert-fire alert-noise \
        prom-reload targets workers-trap test-observability obs

# .env is SOURCED by bash rather than `include`d, so quoting and comments behave
# exactly as they do in a terminal.
#
# DVC talks to Silo directly and reads the AWS_* names, so we map the Silo
# block from .env onto them here. That way one credential block in .env serves
# both MLflow and DVC, and no secret is ever written into .dvc/config.
#
# DVC_PAGER=cat keeps `dvc dag` and `dvc metrics diff` from dropping a
# classroom terminal into `less`.
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

## Week 4 setup — initialise DVC and point the remote at Silo
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

## Week 4 setup — build dataset version 1 (baseline batch only)
data-v1:
	uv run python src/main.py build-data --version 1

## Week 4 setup — build dataset version 2 (baseline + new arrival); what we validate
data-v2:
	uv run python src/main.py build-data --version 2

## Week 4 setup — track the dataset with DVC
dvc-add:
	$(DVC) add data/measurements.csv
	@echo
	@echo "--- data/measurements.csv.dvc ---"
	@cat data/measurements.csv.dvc
	@echo "--- data/.gitignore (DVC wrote this, in data/) ---"
	@cat data/.gitignore

## Week 4 setup — upload the bytes to Silo
dvc-push:
	$(DVC) push

## Pull the bytes back from Silo
dvc-pull:
	$(DVC) pull

## Compare workspace / cache / remote
dvc-status:
	$(DVC) status
	$(DVC) status --cloud

## Week 4 mechanics — prove the round trip: empty cache, checkout FAILS, pull restores
dvc-roundtrip:
	rm -f data/measurements.csv
	rm -rf .dvc/cache
	@echo "--- dvc checkout with an empty cache (expected to FAIL) ---"
	-$(DVC) checkout
	@echo "--- dvc pull (fetches from Silo) ---"
	$(DVC) pull
	uv run python src/main.py verify-data

## Week 5 mechanics — run the ingestion contract and write the verdict
##
## Exits NON-ZERO when the data fails its contract. That is what makes the
## `validate` DVC stage a gate rather than a report.
validate:
	uv run python src/main.py validate

## Week 5 mechanics — the same contract against the corrupted batch
##
## Exits 0 even though the file fails: inspecting a broken file is not an error.
## The exercise is to READ the report, not to make it go away.
validate-broken:
	uv run python src/main.py check-file

## Week 5 mechanics — the training contract, failing then passing
validate-model-input:
	uv run python src/main.py model-input

## Run the declared pipeline (only stale stages re-run) — now ends at `gate`
repro:
	$(DVC) repro

## Exercise 1/2 — the slice table: every group, with its n and its positives.
##
## Reads what `evaluate` already wrote rather than recomputing it, so the table
## you read is byte-for-byte the one the gate acted on.
slices:
	uv run python src/main.py slices

## Exercise 3/4 — the go/no-go decision. DVC stage 4.
##
## Exits NON-ZERO on a NO-GO, which is what stops `dvc repro` and what a CI job
## would notice. The report is written either way — a gate that blocks a release
## and leaves no evidence behind is untriageable.
gate:
	uv run python src/main.py gate

## Exercise 5 — selection rate, TPR and FPR per group, and the three gaps.
fairness:
	uv run python src/main.py fairness

## Exercise 6 — what "worse than what we have" is measured against.
baseline:
	uv run python src/main.py baseline

## Exercise 6 — raise the bar from the current champion. A deliberate act.
baseline-sync:
	uv run python src/main.py baseline-sync

## Exercise 4 — break the MODEL on purpose and watch the release gate hold.
##
## One line of params.yaml, no code. `C: 0.005` over-regularises the logistic
## regression into a genuinely worse model: F1 falls from 0.6341 to 0.5243 while
## ROC-AUC actually RISES. Gate on ROC-AUC and you would have shipped it.
##
## Three assertions matter here, and the third is the one people miss:
##   1. `dvc repro` exits non-zero at the `gate` stage.
##   2. `register` and `promote` refuse, quoting the gate's own reason — the
##      pipeline is not the only door into the registry.
##   3. models/model.pkl is STILL THERE. A failing model gate stops a release,
##      not an investigation. (Contrast `make data-gate-fail`, where the whole
##      point is that no processed data is written at all.)
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

## Exercise 6 — the ratchet, end to end.
##
## Train a genuinely better model (random forest, F1 0.6452 against logistic
## regression's 0.6341), watch it pass, crown it champion, sync the baseline —
## and then watch the SAME logistic regression that shipped this morning become
## a NO-GO this afternoon, because the bar moved. The ratchet only turns one
## way, which is both the point and the risk.
##
## Leaves the workspace back where it started: the champion alias stays on the
## random forest (that promotion was real), but metrics/baseline.json is
## restored, so `make repro` passes again. Undoing a demo is not optional —
## a lab that leaves you in a broken state teaches you to distrust the lab.
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

## Week 5 mechanics — break the DATA on purpose and watch the ingestion gate hold.
##
## Renamed from `gate-fail` in Week 5, because Week 6 has a second gate and the
## contrast between the two is the lesson. This one stops the pipeline BEFORE
## any work happens; `make gate-fail` stops a RELEASE after all of it.
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

## Show recorded metrics
metrics:
	$(DVC) metrics show

## Week 5 mechanics — validate a request payload, then predict. In that order.
##
## Try each: example (legal) | illegal (glucose 0) | swapped (insulin<->bmi) |
## incomplete (no insulin).
predict:
	uv run python src/main.py predict --payload example

## Week 5 mechanics — the three ways a request goes wrong
predict-bad:
	@for case in illegal swapped incomplete; do \
		echo "=================== $$case ==================="; \
		uv run python src/main.py predict --payload $$case; \
	done

## Force a fresh training run so a new MLflow run is created, and attach its
## metrics.
##
## -s/--single-item forces ONLY the named stage; plain `-f train` would re-run
## `prepare` too, because --force applies to the whole upstream chain.
##
## `evaluate` is forced too, so this target always produces a COMPLETE run
## regardless of the graph. Read `dvc.yaml` convention 4 for why the graph now
## makes that redundant: `evaluate` depends on `models/mlflow_run_id.json`, so a
## new run id is what marks it stale. Before that edge existed, the model's
## determinism meant a re-run of `train` wrote a byte-identical model.pkl, so
## `evaluate` was NOT stale and a plain `dvc repro` skipped it — correct caching,
## exactly wrong outcome, and the new run got params and tags but no scores (an
## empty `metrics.f1` column in `make runs-for-data`).
link:
	$(DVC) repro -f -s train
	$(DVC) repro -f -s evaluate
	$(DVC) repro

## Week 4 mechanics — find every MLflow run trained on the current data version
runs-for-data:
	uv run python src/main.py runs-for-data

## Register the model — REFUSES unless reports/gate.json records a GO.
##
## New in Week 6. `dvc repro` already stops at a failing gate, but a human
## typing `make register` has walked around the pipeline entirely. A gate that
## only holds when you use the front door is not a gate; it is a convention.
register:
	uv run python src/main.py register

## Move the `staging` alias. Also gate-aware.
promote:
	uv run python src/main.py promote

## Move `staging` AND `champion` — the deliberate act that raises the bar.
##
## Separated from `promote` in Week 6. Week 5 set both aliases on every
## promotion, which made the baseline move whenever anyone promoted anything,
## which makes a ratchet meaningless.
promote-champion:
	uv run python src/main.py promote --champion

## Walk the chain: alias -> run -> data -> validation -> GATE VERDICT (8 steps)
trace:
	uv run python src/main.py trace

## The whole week, assuming DVC is already initialised.
##
## `dvc repro` now ends at `gate`, so this target proves the gate PASSES rather
## than merely that it exists — and if it ever stops passing, `all` stops here
## instead of registering a model nobody approved.
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

## Run every test (live/dvc tests auto-skip when their prerequisite is absent)
test:
	uv run pytest tests/ -v

## Run only the tests that need neither the stack nor a DVC repo.
##
## Worth noting what this still covers in Week 5: every schema, report,
## sentinel-conversion, gate and payload test. The validation half of this lab
## has no infrastructure dependency at all, because the batches and the
## corrupted file are in Git.
test-fast:
	uv run pytest tests/ -v -m "not live and not dvc"


# ─────────────────────────────────────────────────────────────────────────────
# Week 7 — CI/CT
# ─────────────────────────────────────────────────────────────────────────────

## Lint. Pinned ruff, explicit rule selection -- see the comments in pyproject.
lint:
	uv run ruff check src tests

## THE ENTRY POINT. `ci.yml` and `ct.yml` both call this, and so do you.
##
## This target is the whole of Exercise 2, and the idea is worth more than the
## six lines it takes: a workflow that RE-LISTS your commands is a second copy
## of your build. It drifts from the first one silently, and you find out when
## CI and your laptop disagree about whether the code works -- usually at the
## worst possible moment, and usually while you are arguing that it works fine
## locally.
##
## One definition. Many callers. `tests/test_workflows.py` asserts that both
## workflows really do call it, so the property is enforced rather than hoped
## for.
##
## Note what is NOT here: register, promote, dvc push. Those need the tracking
## server and the object store, and a CI runner has neither. CI stops at the
## gate, which is exactly where its authority ends.
## A runner has no .env. Neither does a student who just cloned the repo.
##
## This lab's .env carries no secrets -- it is ports and local-dev credentials
## for containers that only ever listen on localhost -- so copying the example
## verbatim is honest here. In a real project this step is exactly where
## secrets enter CI, from the platform's secret store, and the example file is
## the documentation of what has to be provided.
## The DVC-tracked dataset is absent on a fresh clone by design -- it is data,
## not source. Rebuild it from the committed batches rather than pulling it.
ensure-data:
	@test -f data/measurements.csv || { \
	  echo "data/measurements.csv is missing -- it is DVC-tracked, so a fresh"; \
	  echo "clone does not have it. Rebuild it from the committed raw batches:"; \
	  echo "    make data-v2"; \
	  echo "(CI does exactly this, which is why it needs no object store.)"; \
	  exit 1; }

ensure-env:
	@test -f .env || { cp .env.example .env; \
	  echo "no .env found -> copied .env.example (defaults; no secrets in this lab)"; }

ci: ensure-env ensure-data lint test-fast repro gate
	@echo
	@echo "CI passed: lint, tests, pipeline, gate."

## Everything ci.yml does, on your machine, in the order the runner does it.
## Use this before pushing; it is cheaper than a red build.
ci-local: ensure-env ensure-data
	@echo "==> lint";     $(MAKE) --no-print-directory lint
	@echo "==> unit";     $(MAKE) --no-print-directory test-unit
	@echo "==> data";     $(MAKE) --no-print-directory test-data
	@echo "==> eval";     $(MAKE) --no-print-directory test-eval
	@echo "==> pipeline"; $(MAKE) --no-print-directory repro
	@echo "==> gate";     $(MAKE) --no-print-directory gate

## What ct.yml does: retrain and gate WITHOUT a code change.
##
## The only difference from `ci-local` is what caused it to run. That is the
## entire distinction between CI and CT, and it is worth noticing that the
## commands are identical -- CT is not a different pipeline, it is the same
## pipeline with a different trigger and a different blast radius.
ct-local: ensure-env ensure-data
	$(MAKE) --no-print-directory repro
	$(MAKE) --no-print-directory gate

## Exercise 6 -- break the model on purpose and watch CI go red at the gate.
## Restores params.yaml afterwards, even if the gate exits non-zero.
ci-fail:
	@cp params.yaml .params.yaml.ci-bak
	@sed -i.tmp 's/^  C: 1.0$$/  C: 0.005/' params.yaml && rm -f params.yaml.tmp
	@grep -q '^  C: 0.005$$' params.yaml || { \
	  echo "FAILED to plant the fault -- check params.yaml indentation"; \
	  mv .params.yaml.ci-bak params.yaml; exit 1; }
	@echo "Planted train.C: 0.005. Running the pipeline exactly as CI does..."
	@set +e; $(MAKE) --no-print-directory ci; rc=$$?; set -e; \
	  echo; echo "\`make ci\` exit code: $$rc  (non-zero is the point)"; \
	  mv .params.yaml.ci-bak params.yaml; \
	  echo "params.yaml restored. Run \`make repro\` to return to a GO."; \
	  test "$$rc" -ne 0 || { echo; \
	    echo "UNEXPECTED: the gate did NOT refuse. Is the pipeline actually running?"; \
	    echo "A green \`ci-fail\` means the demonstration is broken, not that the model is fine."; \
	    exit 1; }

## The gate verdict as markdown, for `$GITHUB_STEP_SUMMARY`.
##
## The formatting lives in gates.py, not in a heredoc inside the workflow: a
## `run:` block is the one place in a project that nothing tests.
gate-summary:
	@uv run python src/main.py gate-summary

## Exercise 1 -- what is actually installed, and how stale are its pins?
ci-explain:
	@uv run python src/main.py ci-explain

## Exercise 4 -- GitHub only executes workflows in .github/workflows at the
## REPOSITORY ROOT. Not configurable, and the reason a first workflow so often
## does nothing at all. These two targets are that rule, made operational.
install-ci:
	@root=$$(git rev-parse --show-toplevel) && mkdir -p "$$root/.github/workflows" && \
	  for f in .github/workflows/*.yml; do \
	    cp "$$f" "$$root/.github/workflows/week11-$$(basename $$f)"; \
	    echo "installed -> .github/workflows/week11-$$(basename $$f)"; \
	  done
	@echo "Commit and push to run them. \`make uninstall-ci\` removes them again."

uninstall-ci:
	@root=$$(git rev-parse --show-toplevel) && \
	  rm -f "$$root"/.github/workflows/week11-*.yml && echo "removed week11-*.yml"

# ── The test pyramid (Exercise 3) ────────────────────────────────────────────
#
# Two axes, and keeping them apart is the exercise. The LAYER (unit/data/eval/
# integration) is what a test asserts; the GUARD (live/dvc) is what it needs.
# Registered and explained in pyproject.toml.

## Layer 1 -- our code is correct. No dataset, no model, no services.
test-unit:
	uv run pytest tests/ -q -m "unit"

## Layer 2 -- the data and its contracts are correct. Week 5's material.
test-data:
	uv run pytest tests/ -q -m "data and not live and not dvc"

## Layer 3 -- the model, its metrics and the release gate. Week 6's material.
test-eval:
	uv run pytest tests/ -q -m "eval and not live and not dvc"

## Layer 4 -- several real components at once. Needs the stack; CI never runs it.
test-integration:
	uv run pytest tests/ -q -m "integration"


# ─────────────────────────────────────────────────────────────────────────────
# Week 8 — Orchestration
# ─────────────────────────────────────────────────────────────────────────────

## Exercise 1 -- run the training flow. Needs the stack UP (`make up`): the
## CLI refuses without a Prefect server, because an unset PREFECT_API_URL
## would start a temporary one and throw the run history away.
flow: ensure-env ensure-data
	uv run python src/main.py flow

## Exercise 2 -- the same flow, with the registry step, against a live stack.
flow-register: ensure-env ensure-data
	uv run python src/main.py flow --push --register

## Exercise 2 (written) -- what each layer owns. Prints the two graphs so you
## can compare what they know: DVC's is about CONTENT, Prefect's about
## EXECUTION.
flow-dvc: ensure-env
	@echo "=== DVC's graph: what is stale? ==="
	@$(DVC) dag
	@echo
	@echo "=== Prefect's graph: what ran, when, how many times, and what then? ==="
	@echo "  Open $(shell grep -E '^PREFECT_API_URL' .env 2>/dev/null | sed 's|.*=||;s|/api||') and look at a flow run."
	@echo "  DVC cannot answer any of those questions; Prefect cannot answer DVC's."

## Exercise 3 -- prove the retry policy is real, not decorative.
flow-retry:
	uv run pytest tests/test_flows.py -q -k "retr or transient or permanent" -v

## Exercise 4 -- a runtime parameter that reaches params.yaml before dvc repro.
##
## Defaults to `impute_strategy=mean`, which re-runs train + evaluate and still
## clears the gate. Try `make flow-params C=0.01` for the other outcome: the
## parameter lands, the pipeline re-runs, and the GATE REFUSES the result --
## which is the system working, not the exercise failing.
##
## Restores params.yaml afterwards. A lab convenience only; a scheduled run
## deliberately leaves the change in place (see write_params).
flow-params: ensure-env ensure-data
	@if [ -n "$(C)" ]; then \
	  uv run python src/main.py flow-params --C $(C); \
	else \
	  uv run python src/main.py flow-params --impute-strategy $(or $(IMPUTE),mean); \
	fi

## Exercise 5 -- partial failure. Breaks `dvc repro` by planting an impossible
## row in a raw batch, so the validate stage refuses INSIDE the flow; then
## shows which tasks ran and which never started.
flow-fail: ensure-env ensure-data
	@cp data/raw/batch_01_baseline.csv .batch.flow-bak
	@printf '99,999,-1,0,0,0,0,0,2,2099-01-01\n' >> data/raw/batch_01_baseline.csv
	@echo "Planted an impossible row in a raw batch. Running the flow..."
	@echo "(The fault is in the DATA, so it fails INSIDE the flow -- at the"
	@echo " validate stage -- rather than before it starts. That is what makes"
	@echo " this a partial failure rather than a crash.)"
	@echo
	@set +e; uv run python src/main.py flow; rc=$$?; set -e; \
	  echo; echo "flow exit code: $$rc  (non-zero is the point)"; \
	  mv .batch.flow-bak data/raw/batch_01_baseline.csv; \
	  $(MAKE) --no-print-directory data-v2 >/dev/null; \
	  $(DVC) add data/measurements.csv >/dev/null 2>&1; \
	  echo "raw batch, dataset and DVC pointer restored."; \
	  echo "  (build_dataset ran on the corrupted batch, so the pointer moved too --"; \
	  echo "   a demonstration that mutates tracked state has to undo ALL of it.)"; \
	  echo; echo "reports/last_run.txt -- the failure path reported too:"; \
	  sed 's/^/  /' reports/last_run.txt 2>/dev/null || echo "  (nothing written)"; \
	  test "$$rc" -ne 0 || { echo "UNEXPECTED: the flow did not fail."; exit 1; }

## Exercise 6 -- a scheduled deployment. Ctrl-C to stop.
serve: ensure-env ensure-data
	uv run python src/main.py serve --cron "$(or $(CRON),*/5 * * * *)"

## Open the Prefect UI.
prefect-ui:
	@echo "http://127.0.0.1:$${PREFECT_PORT:-5520}"

## Just the Week 8 tests.
test-flows:
	uv run pytest tests/test_flows.py tests/test_scope.py -q


# ─────────────────────────────────────────────────────────────────────────────
# Week 9 — Serving & deployment
# ─────────────────────────────────────────────────────────────────────────────

## Exercise 1 -- the server you get for ZERO code.
##
## `--env-manager local` stops MLflow rebuilding the model's environment from
## its recorded python_env.yaml on every start. Worth knowing what that flag
## suppresses: it is the whole point of the cold open. We are choosing to trust
## that this interpreter matches the one the model was trained in.
serve-mlflow: ensure-env
	uv run mlflow models serve \
	  -m "models:/$(MLFLOW_REGISTERED_MODEL_NAME)@$(MLFLOW_CHAMPION_ALIAS)" \
	  --env-manager local -p 5540 --host 127.0.0.1

## Exercise 2 -- your own service. Needs no stack: it reads models/model.pkl.
##
## NAMED `serve-api`, not `serve`, because Week 8 already has a `serve` target
## for the Prefect deployment. make does not warn loudly about a redefinition
## (it prints "overriding commands for target" and carries on), so a collision
## silently replaces the earlier week's target. Worth checking whenever a lab
## inherits a Makefile.
serve-api: ensure-data
	uv run python src/main.py serve-api --port $(or $(PORT),5541)

## Exercise 3 -- batch vs online, measured, in one process.
bench: ensure-data
	uv run python src/main.py bench

## Exercise 4 -- build the image, BAKING the model and its provenance in.
##
## Reads the champion's identity from the registry if the stack is up, and
## falls back to the local gate report if it is not. Either way the image
## RECORDS which path it took, so a container can never claim a provenance it
## does not have.
##
## CHANGED IN WEEK 11, and the investigation is worth more than the change.
##
## Weeks 9 and 10 set `DOCKER_BUILDKIT=0` to keep the build output plain for a
## classroom. On Docker Engine 29.6.2 this target printed the legacy builder's
## deprecation banner and then produced nothing at all for **26 minutes**.
##
## THE FIRST DIAGNOSIS WAS WRONG, and recording that is the point. It looked
## like the deprecated flag hanging, and that is what got written down. Then the
## killed process's stderr arrived:
##
##     Can't add file .../solution/.dvc to tar: io: read/write on closed pipe
##
## ...which says it was never stuck. It was building the CONTEXT TARBALL. Run
## `du -sh .` in this directory: **783 MB, of which 780 MB is .venv/**, and there
## was no `.dockerignore`. `docker build` uploads the whole context to the daemon
## BEFORE the first instruction; the legacy builder does that as one serial tar
## with no progress output until it finishes.
##
## Re-measured against an empty context, `DOCKER_BUILDKIT=0` builds `FROM alpine`
## + `RUN echo hi` in **5.6 seconds**. It does not hang. And with the
## `.dockerignore` this week adds, the context is **2.9 MB** and the legacy
## builder finishes this very image in **37 seconds**.
##
## So there are two lessons and the second is the real one:
##   1. BuildKit is still the right default — the legacy builder is deprecated
##      and its removal is announced, and `--progress=plain` gives back the plain
##      log the flag was being kept for.
##   2. **BuildKit did not fix the defect; it HID it.** A 783 MB context is a
##      defect either way, and the fast tool is the one that let it survive ten
##      weeks unnoticed. Week 9 wrote "a build context is exactly what you put in
##      it" when README.md was MISSING from it; this is the same sentence from
##      the other end of the range.
image: ensure-env
	@set -e; \
	  eval "$$(uv run python src/main.py bake-info)"; \
	  echo "baking: version=$$MODEL_VERSION run=$$RUN_ID gate=$$GATE_VERDICT source=$$MODEL_SOURCE"; \
	  test "$$GATE_VERDICT" = "GO" || { echo; \
	    echo "REFUSING to build: the recorded gate verdict is '$$GATE_VERDICT'."; \
	    echo "Week 6 said only a GO model may be released. A container IS a release,"; \
	    echo "so the gate applies here too — this is the third door into production"; \
	    echo "and it needs the same lock as register and promote."; exit 1; }; \
	  docker build --progress=plain -f serve.Dockerfile -t diabetes-api:local \
	    --build-arg MODEL_VERSION="$$MODEL_VERSION" --build-arg RUN_ID="$$RUN_ID" \
	    --build-arg GATE_VERDICT="$$GATE_VERDICT" --build-arg MODEL_SOURCE="$$MODEL_SOURCE" .

## Run the image directly, with NOTHING else running.
run-image:
	docker run --rm -p $(or $(PORT),5542):8000 --name diabetes-api diabetes-api:local

## Exercise 5 (Week 9) -- a local cluster.
##
## CHANGED IN WEEK 10: the cluster is now created from k8s/kind-cluster.yaml,
## which bind-mounts ./model-store into the node and maps a node port to 5550.
## Week 9's bare `kind create cluster` still works for Week 9's exercises; it
## just cannot serve a model the cluster has to FETCH, because the node cannot
## see a directory nobody mounted.
kind-up:
	kind create cluster --config k8s/kind-cluster.yaml
	kubectl cluster-info --context kind-mlops

kind-down:
	kind delete cluster --name mlops

## Side-load the image, then apply the manifests.
##
## `kind load` is NOT optional: kind's nodes are containers with their own
## image store, so an image in your local Docker daemon is invisible to them.
## Without it the pods sit in ErrImagePull, pointing at a registry that has
## never heard of this image.
## `kubectl apply -f k8s/` was enough in Week 9, when the directory held two
## files. It now also holds a kind cluster config and this week's KServe
## objects, and `apply -f <dir>` applies EVERYTHING in the directory — so the
## paths are explicit. A directory is not an interface.
k8s-deploy:
	kind load docker-image diabetes-api:local --name mlops
	kubectl apply -f k8s/deployment.yaml -f k8s/service.yaml
	kubectl rollout status deployment/diabetes-api --timeout=120s
	@echo
	@echo "  kubectl port-forward svc/diabetes-api 5543:80"
	@echo "  curl localhost:5543/health"

k8s-status:
	@kubectl get pods,svc,endpoints -l app=diabetes-api

## Exercise 6 -- a rolling update, with the readiness probe holding traffic.
k8s-rollout:
	kubectl rollout restart deployment/diabetes-api
	kubectl rollout status deployment/diabetes-api --timeout=120s
	@kubectl get pods -l app=diabetes-api


# ─────────────────────────────────────────────────────────────────────────────
# Week 10 — Rollout strategies (KServe)
# ─────────────────────────────────────────────────────────────────────────────

# The platform, pinned. Two numbers and a hash, and all three matter:
# a rollout lab whose control plane changed under it is not reproducible, and
# a 2.5 MB shell script from the internet is exactly the supply-chain lesson
# Week 9 opened with. Downloaded once into .kserve/ (git-ignored), CHECKSUMMED,
# then run.
KSERVE_VERSION  = v0.20.0
KSERVE_INSTALLER = kserve-knative-mode-full-install-with-manifests.sh
KSERVE_SHA256   = 3316776068a5d52ef74ce0dfe152f690102ba226ac8e67e9bb6fe8ebcfa39ff2
KSERVE_URL      = https://github.com/kserve/kserve/releases/download/$(KSERVE_VERSION)/$(KSERVE_INSTALLER)

# One name for the cluster all week, and it is Week 9's cluster.
CLUSTER   = mlops
ISVC      = diabetes
# The Host header the ingress gateway routes on. KServe assigns it; `make
# isvc-url` prints whatever it actually is, and this is the default shape.
ISVC_HOST = $(ISVC).default.example.com
GATEWAY   = http://127.0.0.1:5550
# The address the in-cluster Jobs use. NOT the gateway, and not a port-forward:
# Week 9 measured a healthy rolling update through `kubectl port-forward` and
# saw a 62% error rate, because port-forward holds a connection to ONE pod.
# Every number this week is measured from inside the cluster.
ISVC_INTERNAL = http://$(ISVC)-predictor.default.svc.cluster.local

## Exercise 1 -- install the control plane. ~5 minutes, ~2.5 GB of images.
##
## Installs, in this order: cert-manager, Istio, the Knative Operator, Knative
## Serving, KServe. FIVE new moving parts to get a traffic split, which is the
## honest price of `canaryTrafficPercent` and belongs on the slide next to the
## eight lines of YAML it enables.
##
## KNATIVE MODE, deliberately. The sibling installer ("standard mode") is
## smaller and has no Knative — and in standard mode `canaryTrafficPercent` is
## SILENTLY IGNORED (kserve/kserve#5335). A field that is accepted and does
## nothing is the worst failure mode available, and the rollout strategy you can
## use is a function of the deployment mode you installed.
kserve-install: .kserve/$(KSERVE_INSTALLER)
	@echo "==> installing KServe $(KSERVE_VERSION) (knative mode) into kind cluster '$(CLUSTER)'"
	@kubectl config use-context kind-$(CLUSTER) >/dev/null
	NO_COLOR=1 bash .kserve/$(KSERVE_INSTALLER)
	@echo
	@echo "==> exposing the ingress gateway on $(GATEWAY)"
	@echo "    kind maps host 5550 -> node 30080 (k8s/kind-cluster.yaml), so the"
	@echo "    gateway's nodePort is pinned to 30080. A LoadBalancer Service has"
	@echo "    no external IP on a laptop; this is the cheapest honest substitute."
	kubectl patch svc istio-ingressgateway -n istio-system \
	  -p '{"spec":{"ports":[{"name":"http2","port":80,"nodePort":30080}]}}'
	@$(MAKE) --no-print-directory kserve-status

## Download the installer once, and VERIFY it before running it.
.kserve/$(KSERVE_INSTALLER):
	@mkdir -p .kserve
	curl -sSL -o $@ $(KSERVE_URL)
	@echo "$(KSERVE_SHA256)  $@" | shasum -a 256 -c - || { \
	  echo "CHECKSUM MISMATCH -- refusing to run it. Delete .kserve/ and retry,"; \
	  echo "or check whether the release was re-cut."; rm -f $@; exit 1; }

## What is running, and which versions.
kserve-status:
	@kubectl get pods -n kserve -n knative-serving 2>/dev/null | head -1 >/dev/null || true
	@echo
	@for ns in cert-manager istio-system knative-serving kserve; do \
	  printf "  %-16s %s pod(s) ready\n" "$$ns" \
	    "$$(kubectl get pods -n $$ns --no-headers 2>/dev/null | grep -c ' Running ')"; \
	done
	@echo
	@kubectl get crd 2>/dev/null | grep -E 'inferenceservices|revisions.serving' | sed 's/^/  /'
	@echo
	@echo "  kubectl explain inferenceservice.spec.predictor   <- read the vocabulary"

## Remove the control plane, keeping the cluster.
kserve-uninstall:
	NO_COLOR=1 bash .kserve/$(KSERVE_INSTALLER) --uninstall

# ── The model store (Exercise 2) ─────────────────────────────────────────────

## Publish the CURRENT model into the store as VERSION (default v1).
##
## Refuses a non-GO verdict. `FORCE=1` publishes anyway and records the real
## verdict in provenance.json -- that is Exercise 4's exhibit, not a loophole.
##
## A model store is the FOURTH door into production, after `register`, `promote`
## and `docker build`, and it is the widest: publishing is a file copy.
model-publish: ensure-data
	uv run python src/main.py model-publish --store-version $(or $(VERSION),v1) \
	  $(if $(FORCE),--force,)

## Retrain with a different family/C, publish it, and put params.yaml back.
##
## The same pattern as Week 6's `make ratchet`: mutate params.yaml, run the
## pipeline, act on the result, restore. A demonstration that mutates tracked
## state has to undo ALL of it (Week 8, lesson 3).
##
##   make model-publish-variant VERSION=v2 FAMILY=rf
##   make model-publish-variant VERSION=v3 C=0.001 FORCE=1
model-publish-variant: ensure-data
	@cp params.yaml .params.yaml.w11-bak
	@if [ -n "$(FAMILY)" ]; then \
	  uv run python -c "import pathlib; p=pathlib.Path('params.yaml'); p.write_text(p.read_text().replace('  family: logreg', '  family: $(FAMILY)'))"; fi
	@if [ -n "$(C)" ]; then \
	  uv run python -c "import pathlib; p=pathlib.Path('params.yaml'); p.write_text(p.read_text().replace('  C: 1.0', '  C: $(C)'))"; fi
	@echo "--- pipeline with the variant params (the gate runs as usual) ---"
	-$(DVC) repro
	@set +e; $(MAKE) --no-print-directory model-publish VERSION=$(VERSION) FORCE=$(FORCE); rc=$$?; set -e; \
	  mv .params.yaml.w11-bak params.yaml; \
	  echo "params.yaml restored."; \
	  $(DVC) repro >/dev/null 2>&1 || true; \
	  test "$$rc" -eq 0 || { echo "publish refused (exit $$rc)."; exit $$rc; }

## What is in the store, and what each version claims to be.
store-list:
	uv run python src/main.py store-list

# ── The InferenceService (Exercises 1, 2, 3) ──────────────────────────────────

## Side-load the image, create the PV/PVC, apply the InferenceService.
##
## `kind load` is still required, exactly as in Week 9: the node has its own
## image store and has never heard of a locally-built image.
isvc-deploy:
	kind load docker-image diabetes-api:local --name $(CLUSTER)
	kubectl apply -f k8s/model-store.yaml
	kubectl apply -f k8s/inferenceservice.yaml
	kubectl wait --for=condition=Ready inferenceservice/$(ISVC) --timeout=300s
	@$(MAKE) --no-print-directory isvc-url

## Exercise 3 -- a second revision, taking 10% of the traffic.
##
## Two lines differ from k8s/inferenceservice.yaml: the STORAGE_URI and
## `canaryTrafficPercent: 10`. Everything else, including the IMAGE, is
## identical -- and `tests/test_isvc_manifests.py` asserts that.
## VERSION= overrides which store version the canary serves (default v2).
## Exercise 4 uses `VERSION=v3` for the model the gate refused.
##
## One `sed`, and it is deliberate: a `kubectl patch --type merge` on a CRD
## REPLACES the whole containers list rather than merging it, so patching one env
## var means re-sending the entire container spec. Templating a manifest is a
## real need and Helm/Kustomize exist to meet it; both are out of scope here, and
## one substitution is honest about what they are for.
isvc-canary:
	sed 's|pvc://diabetes-models/v2|pvc://diabetes-models/$(or $(VERSION),v2)|' \
	  k8s/inferenceservice-canary.yaml | kubectl apply -f -
	kubectl wait --for=condition=Ready inferenceservice/$(ISVC) --timeout=300s
	@$(MAKE) --no-print-directory isvc-status

## The split, the revisions, and the pods. `kubectl get isvc` is the first
## command to run and `kubectl get revision` the second -- a Deployment cannot
## answer either question, which is the week in one line.
isvc-status:
	@echo
	@kubectl get isvc $(ISVC)
	@echo
	@kubectl get revision -l serving.knative.dev/service=$(ISVC)-predictor
	@echo
	@kubectl get pods -l serving.knative.dev/service=$(ISVC)-predictor
	@echo
	@echo "  traffic, as the control plane records it:"
	@kubectl get isvc $(ISVC) -o jsonpath='{range .status.components.predictor.traffic[*]}    {.revisionName} {.percent}%{"\t"}tag={.tag}{"\n"}{end}'

## The URL KServe assigned, and how to reach it from a laptop.
isvc-url:
	@echo
	@echo "  external : $$(kubectl get isvc $(ISVC) -o jsonpath='{.status.url}')"
	@echo "  internal : $$(kubectl get isvc $(ISVC) -o jsonpath='{.status.address.url}')"
	@echo
	@echo "  The hostname is not in DNS, so send the Host header to the gateway:"
	@echo "    curl -s -H 'Host: $(ISVC_HOST)' $(GATEWAY)/health"
	@echo

## Sanity-check the endpoint from the host, through the gateway.
isvc-health:
	@curl -s -H "Host: $(ISVC_HOST)" $(GATEWAY)/health

## Tear down this week's objects, leaving the cluster and KServe in place.
isvc-down:
	-kubectl delete -f k8s/inferenceservice.yaml
	-kubectl delete -f k8s/model-store.yaml

# ── Measuring (Exercises 3 and 6) ─────────────────────────────────────────────

## Exercise 3 -- count which revision answered, N requests, from INSIDE the
## cluster. DECLARED= the canaryTrafficPercent you asked for, so the output can
## put the measured share next to it with its sampling error.
split-measure:
	@$(MAKE) --no-print-directory _job JOB=split-measure \
	  ARGS="split-measure --url $(ISVC_INTERNAL) --requests $(or $(N),200) --declared $(or $(DECLARED),10)"

## Exercise 6 -- the same endpoint at rising concurrency.
loadtest:
	@$(MAKE) --no-print-directory _job JOB=loadtest \
	  ARGS="loadtest --url $(ISVC_INTERNAL) --requests $(or $(N),200) --concurrency-levels $(or $(LEVELS),1,4,16,64)"

## Exercise 4 -- smoke-test the CANARY revision specifically, by tag.
##
## Not the split: firing requests at a 90/10 URL and hoping you hit the new
## revision is not a test. Tag routing gives the canary its own address, which
## is what makes it testable BEFORE it is promoted.
smoke:
	@$(MAKE) --no-print-directory _job JOB=smoke \
	  ARGS="smoke --url http://latest-$(ISVC)-predictor.default.svc.cluster.local $(if $(VERSION),--store-version $(VERSION),)"

## The same suite, in-process, against a model from the store. No cluster, no
## Docker, no server -- which is why it also runs in the autograder.
smoke-local:
	MODEL_PATH=$(PWD)/model-store/$(or $(VERSION),v1)/model.pkl \
	  uv run python src/main.py smoke --store-version $(or $(VERSION),v1)

## Run one of this lab's commands as a Job in the cluster, print its log, and
## clean up. The image is the one already loaded -- the load generator ships
## with the service, so there is nothing else to build.
## Polls for EITHER outcome rather than waiting for success, then exits with the
## job's own verdict.
##
## Both halves matter. `kubectl wait --for=condition=Complete` accepts only one
## condition, so waiting for success means a FAILED job sits there until the
## timeout -- five minutes of nothing, for a result that was known in two
## seconds. And a `make smoke` that prints FAIL and exits 0 is the exact defect
## this course keeps naming: Week 4's check_locks.sh, Week 7's ci-fail, both
## green while checking nothing. A smoke test whose failure exits 0 is a comment.
_job:
	-@kubectl delete job w11-$(JOB) --ignore-not-found >/dev/null 2>&1
	@args=$$(printf '"%s", ' $(ARGS) | sed 's/, $$//'); \
	  sed -e 's|__NAME__|w11-$(JOB)|' -e "s|__ARGS__|$$args|" k8s/job.yaml \
	  | kubectl apply -f - >/dev/null
	@ok=""; for _ in $$(seq 1 150); do \
	  s=$$(kubectl get job w11-$(JOB) -o jsonpath='{.status.succeeded}' 2>/dev/null); \
	  f=$$(kubectl get job w11-$(JOB) -o jsonpath='{.status.failed}' 2>/dev/null); \
	  if [ -n "$$s" ]; then ok=yes; break; fi; \
	  if [ -n "$$f" ]; then ok=no; break; fi; \
	  sleep 2; done; \
	  kubectl logs job/w11-$(JOB) 2>/dev/null; \
	  kubectl delete job w11-$(JOB) --ignore-not-found >/dev/null; \
	  test "$$ok" = "yes" || { echo; \
	    echo "  $(JOB) FAILED in the cluster (exit non-zero). The log above is the"; \
	    echo "  evidence, and a non-zero exit here is what a rollout script would"; \
	    echo "  branch on: do NOT promote."; exit 1; }

# ── Promotion and rollback (Exercise 5) ───────────────────────────────────────

## Promote the canary: REMOVE canaryTrafficPercent, and the latest revision
## takes 100%. The old revision stays in the history and scales to zero.
promote-canary:
	kubectl patch isvc $(ISVC) --type json \
	  -p '[{"op": "remove", "path": "/spec/predictor/canaryTrafficPercent"}]'
	@sleep 5
	@$(MAKE) --no-print-directory isvc-status

## Roll back: pin 100% to the previously rolled-out revision.
##
## `canaryTrafficPercent: 0` is not "delete the canary". The new revision stays
## up, stays addressable by its tag, and keeps zero traffic -- which is what
## blue/green looks like once you have tags. Two other ways to roll back, and
## the exercise is to compare them:
##   make rollback-reapply    re-apply the previous manifest. Note this rolls
##                            FORWARD: a NEW revision that happens to serve the
##                            old model, with a new pod and a cold start.
##   kubectl delete revision  NOT a rollback. The Configuration still names the
##                            revision, so the controller recreates it — measured:
##                            back and serving the same bad model in ~20s.
rollback:
	kubectl patch isvc $(ISVC) --type merge \
	  -p '{"spec": {"predictor": {"canaryTrafficPercent": 0}}}'
	@sleep 5
	@$(MAKE) --no-print-directory isvc-status

rollback-reapply:
	kubectl apply -f k8s/inferenceservice.yaml
	@sleep 5
	@$(MAKE) --no-print-directory isvc-status

## Just the Week 10 tests.
test-rollout:
	uv run pytest tests/test_isvc_manifests.py tests/test_rollout.py \
	  tests/test_smoke_suite.py tests/test_loadtest.py tests/test_scope.py -q


# ─────────────────────────────────────────────────────────────────────────────
# Week 11 — Observability
# ─────────────────────────────────────────────────────────────────────────────

# Where things listen. Container-internal ports stay at each tool's default;
# only the HOST ports move into the 55xx block. Week 9 took 5540-5543, Week 10
# took 5550, so this week takes 5560/5561/5562.
PROM_URL  = http://127.0.0.1:$(or $(PROMETHEUS_PORT),5560)
GRAF_URL  = http://127.0.0.1:$(or $(GRAFANA_PORT),5561)
API_URL   = http://127.0.0.1:$(or $(API_PORT),5562)

## Exercise 1 -- read the exposition format, in-process.
##
## No Docker, no Prometheus, no server. Sends five requests through a TestClient
## first, because a page of zeroes teaches nothing: a counter at 3 after three
## requests is what shows you what a counter IS.
metrics-show: ensure-data
	@uv run python src/main.py metrics-show $(if $(FILTER),--filter '$(FILTER)',)

## Exercise 1 -- the same thing over HTTP, on the host.
##
## `make serve-api` (Week 9) then, in another terminal:
##   curl -s localhost:5541/metrics | head -40
## One second per edit. The container comes later, when there is something to
## scrape it.

## Exercise 2 -- start the service being observed.
##
## It is behind a Compose PROFILE, so `make up` deliberately leaves it down and
## Prometheus shows the target as DOWN from the first moment. That is not a
## broken lab: `up{job="diabetes-api"} == 0` is the first metric and the first
## alert, and it is what a pull-based collector knows that a ratio-based SLI
## structurally cannot.
##
## Needs `make image` first -- the image is built by a target that REFUSES on a
## non-GO gate verdict (Week 9), which is why compose runs it rather than
## building it.
api-up:
	@docker image inspect diabetes-api:local >/dev/null 2>&1 || { \
	  echo "diabetes-api:local does not exist yet."; \
	  echo "Build it first:  make image"; \
	  echo "(It refuses to build on a non-GO gate verdict -- a container is a"; \
	  echo " release, and Week 6's gate applies to every door into production.)"; \
	  exit 1; }
	docker compose --profile api up -d --wait api
	@echo
	@echo "  api        $(API_URL)/health"
	@echo "  prometheus $(PROM_URL)/targets   <- watch it go UP"
	@echo "  grafana    $(GRAF_URL)"

## Exercise 4 -- stop it, and watch ServiceDown go pending -> firing.
api-down:
	docker compose --profile api stop api
	@echo
	@echo "  Now watch $(PROM_URL)/alerts"
	@echo "  ServiceDown appears PENDING within a scrape interval (5s for this job)"
	@echo '  and turns FIRING one minute later -- that minute is the rule"s "for:",'
	@echo "  and it is what stops every deploy and hiccup from paging somebody."

## The structured access log: the same requests, in their other shape.
api-logs:
	docker compose logs --no-log-prefix api | grep '"event": "http_request"' | tail -20

## Exercise 2 -- one request, two shapes, side by side.
logs-json:
	@echo "=== the METRIC: 200 requests, aggregated into a handful of numbers ==="
	@curl -s $(API_URL)/metrics | grep '^http_requests_total' || \
	  { echo "  (the api container is not up -- make api-up)"; exit 1; }
	@echo
	@echo "=== the LOG: one line per request, with things a metric cannot hold ==="
	@docker compose logs --no-log-prefix api 2>/dev/null \
	  | grep '"event": "http_request"' | tail -3 \
	  | (command -v jq >/dev/null && jq . || cat)
	@echo
	@echo "  The request_id is the difference. Free in a log line; one time series"
	@echo "  per request, forever, as a metric label. That is the whole distinction."

## Exercise 2 -- generate traffic with a KNOWN composition.
##
## Not a load test (that is `make loadtest`, Week 10). This drives the service at
## a modest steady rate with a controlled mix, so that when the error-rate panel
## reads 5% you can say "yes, because I asked for 5%" rather than looking at a
## graph and hoping.
##
##   make traffic N=600 RATE=30 MIX=valid=8,violation=1,notfound=1
traffic:
	@uv run python src/main.py traffic --url $(API_URL) \
	  --requests $(or $(N),300) --rate $(or $(RATE),20) \
	  $(if $(MIX),--mix '$(MIX)',) --seed $(or $(SEED),42)

## Traffic while the service is down (not used by an exercise).
##
## The API has no route that returns a 5xx (correctly -- a service that can be
## made to fail on demand is a service with a bug in it), so the honest way to
## burn the AVAILABILITY budget is to take the service away: with the container
## stopped, every request is a transport failure and `up` is 0.
##
## The rate-based rules need a few minutes of data before a 1h window says
## anything, which is itself the lesson: burn-rate alerting trades detection
## speed for not waking you up over nothing. `make alerts-test` is how you
## verify the rule without waiting an hour.
traffic-errors:
	@echo "--- stopping the service, then sending traffic at it anyway ---"
	@$(MAKE) --no-print-directory api-down
	-@uv run python src/main.py traffic --url $(API_URL) --requests 60 --rate 10
	@echo
	@echo "--- and back up ---"
	@$(MAKE) --no-print-directory api-up

## Exercise 2 -- the queries, with what each one is for.
promql:
	@echo
	@echo "  Open $(PROM_URL)/graph and paste these in turn."
	@echo
	@echo "  1. up{job=\"diabetes-api\"}"
	@echo "       1 or 0. You get this without instrumenting anything."
	@echo
	@echo "  2. http_requests_total"
	@echo "       The raw counter. Look at it once, then never again: its value"
	@echo "       depends on when the process started."
	@echo
	@echo "  3. rate(http_requests_total[1m])"
	@echo "       Per-second rate. Handles a restart as a reset, not as a huge"
	@echo "       negative spike. The window must span at least two scrapes."
	@echo
	@echo "  4. sum by (status) (rate(http_requests_total[1m]))"
	@echo "       Aggregated across everything except status. 'sum by' is how you"
	@echo "       choose which dimensions survive."
	@echo
	@echo "  5. sum(rate(http_requests_total{status=~\"5..\"}[5m]))"
	@echo "     / sum(rate(http_requests_total[5m]))"
	@echo "       The availability SLI. Note it is a RATIO of events, not uptime."
	@echo
	@echo "  6. histogram_quantile(0.95,"
	@echo "       sum by (le) (rate(http_request_duration_seconds_bucket[5m])))"
	@echo "       p95. rate the buckets, sum by le, THEN take the quantile."
	@echo "       Any other order is wrong, because percentiles do not average."
	@echo
	@echo "  7. sum by (check) (rate(model_contract_violations_total[5m]))"
	@echo "       Week 5's contract, in production, as a rate."
	@echo

## Exercise 1 -- the cardinality experiment: route template vs raw path.
cardinality: ensure-data
	@uv run python src/main.py cardinality --requests $(or $(N),50)

## Exercise 3 -- the dashboard, and the URLs.
grafana:
	@echo
	@echo "  $(GRAF_URL)          (anonymous Editor access -- a lab convenience)"
	@echo "  $(GRAF_URL)/d/diabetes-service"
	@echo
	@echo "  Provisioned from grafana/. Grafana does not save a UI edit: copy the"
	@echo "  dashboard JSON into grafana/dashboards/diabetes-service.json, and"
	@echo "  Grafana reloads the file within 10s."
	@echo "  Every panel carries its teaching note in its description; hover the (i)."
	@echo

prometheus-ui:
	@echo "  $(PROM_URL)/graph     PromQL"
	@echo "  $(PROM_URL)/targets   who is being scraped, and is it working"
	@echo "  $(PROM_URL)/alerts    inactive / pending / firing"
	@echo "  $(PROM_URL)/rules     what is being evaluated, and when it last ran"

## Exercise 3 -- the drift guard, on its own.
##
## Rename a metric in metrics.py and run this: the panel goes silently EMPTY
## (which looks exactly like "no traffic") and this goes red. That is the whole
## reason a dashboard belongs in git next to the code that feeds it.
dashboard-check:
	uv run pytest tests/test_dashboard.py -q

## Exercise 4 -- the promise, the budget, and the burn-rate table.
slo-budget:
	@uv run python src/main.py slo-budget

## Is the configuration even loadable? Runs promtool from INSIDE the Prometheus
## image, so this week adds no host tool.
alerts-check:
	docker compose run --rm --no-deps --entrypoint promtool prometheus \
	  check config /etc/prometheus/prometheus.yml

## Exercise 4 -- run the promtool tests in prometheus/tests/alerts_test.yml.
##
## `promtool test rules` runs the real rules against synthetic series and
## checks which alerts fire at which times. No server, no clock.
alerts-test:
	docker compose run --rm --no-deps --entrypoint promtool prometheus \
	  test rules /etc/prometheus/tests/alerts_test.yml

## ...and the negative test, because a green suite proves nothing until you have
## seen it go red. Loosens ServiceDown's `for:` to 5m and re-runs: the test that
## asserts it fires at 2m5s must now FAIL.
alerts-test-fail:
	@cp prometheus/rules/service.yml .service.yml.bak
	@uv run python -c "import pathlib; p=pathlib.Path('prometheus/rules/service.yml'); p.write_text(p.read_text().replace('        for: 1m', '        for: 5m', 1))"
	@echo 'Planted "for: 5m" on ServiceDown. The suite must now FAIL.'
	@set +e; $(MAKE) --no-print-directory alerts-test; rc=$$?; set -e; \
	  mv .service.yml.bak prometheus/rules/service.yml; \
	  echo; echo "promtool exit code: $$rc  (non-zero is the point)"; \
	  echo "service.yml restored."; \
	  test "$$rc" -ne 0 || { echo; \
	    echo "UNEXPECTED: the rule test PASSED with a broken rule. The suite is"; \
	    echo "not testing what it claims to test, which is worse than no suite."; \
	    exit 1; }

## Exercise 4 -- fire one for real, and time it.
alert-fire:
	@echo "=== 1. the alert is inactive ==="
	@curl -s $(PROM_URL)/api/v1/rules | \
	  uv run python -c "import json,sys; [print(f\"    {r['name']:<32} {r.get('state','-')}\") for g in json.load(sys.stdin)['data']['groups'] for r in g['rules'] if r['type']=='alerting']"
	@echo
	@echo "=== 2. stop the service ==="
	@$(MAKE) --no-print-directory api-down
	@echo
	@echo "=== 3. watch it change state (polling every 5s for 2 minutes) ==="
	@start=$$(date +%s); \
	 for _ in $$(seq 1 24); do \
	   state=$$(curl -s $(PROM_URL)/api/v1/rules | \
	     uv run python -c "import json,sys; print(next((r.get('state','-') for g in json.load(sys.stdin)['data']['groups'] for r in g['rules'] if r.get('name')=='ServiceDown'), 'unknown'))" 2>/dev/null); \
	   printf "    +%3ds  ServiceDown: %s\n" "$$(( $$(date +%s) - start ))" "$$state"; \
	   test "$$state" = "firing" && break; \
	   sleep 5; \
	 done
	@echo
	@echo "=== 4. put it back, and watch it resolve ==="
	@$(MAKE) --no-print-directory api-up
	@echo
	@echo '  The gap between PENDING and FIRING is the rule"s "for: 1m". Without it,'
	@echo "  every deploy pages somebody. With it, a real outage is announced one"
	@echo "  minute late -- and that trade is the single most effective anti-fatigue"
	@echo "  control Prometheus has."

## Not an exercise -- how often would each rule have woken somebody?
alert-noise:
	@uv run python src/main.py alert-noise --seed $(or $(SEED),42)

## Apply a rule change without restarting anything (~1s).
prom-reload:
	@curl -s -X POST $(PROM_URL)/-/reload && echo "  reloaded" || \
	  echo "  reload failed -- is prometheus up, and was --web.enable-lifecycle set?"

## Who is being scraped, and is it working. The first place to look, always.
targets:
	@curl -s $(PROM_URL)/api/v1/targets | \
	  uv run python -c "import json,sys; [print(f\"  {t['labels']['job']:<16} {t['scrapeUrl']:<34} {t['health']:<8} {t.get('lastError','')}\") for t in json.load(sys.stdin)['data']['activeTargets']]"

## The multi-worker trap, reproduced. Two minutes, and worth them.
##
## prometheus_client's default registry is PER PROCESS. Four uvicorn workers
## means four independent sets of counters, and each scrape is answered by
## whichever one accepted the connection.
##
## MEASURED on the reference machine: 200 requests, 4 workers, 30 scrapes of the
## same counter returned 45 (five times) and 155 (twenty-four times). They add to
## 200, and NEITHER IS EVER THE TRUTH. rate() reads every 155 -> 45 drop as a
## counter reset and then counts the climb back as 110 requests that never
## happened.
##
## Repeat it WITHOUT --no-keepalive and you get the quieter, worse variant: every
## scrape reuses one connection, the number is perfectly stable, and it is still
## wrong (35 against a true 40). A wrong number that looks unstable gets
## investigated. A wrong number that looks stable gets used.
##
## Runs the whole experiment and stops. The fix this lab uses is one worker per
## container; the library's `multiprocess` mode is the other answer.
workers-trap: ensure-data
	@echo "Starting uvicorn with FOUR workers on 5599..."
	@uv run uvicorn week_11_observability.api:app --host 127.0.0.1 --port 5599 --workers 4 \
	  > /tmp/w11-workers.log 2>&1 & \
	  sleep 12; \
	  P='{"pregnancies":6,"glucose":148,"blood_pressure":72,"skin_thickness":35,"insulin":125,"bmi":33.6,"diabetes_pedigree":0.627,"age":50}'; \
	  for i in $$(seq $(or $(N),200)); do \
	    curl -s --no-keepalive -X POST localhost:5599/predict \
	      -H 'content-type: application/json' -d "$$P" > /dev/null; done; \
	  echo; echo "  $(or $(N),200) requests sent. Thirty scrapes of ONE counter:"; echo; \
	  for i in $$(seq 30); do \
	    curl -s --no-keepalive localhost:5599/metrics \
	    | grep '^http_requests_total{method="POST",route="/predict",status="200"}' \
	    | awk '{print $$2}'; done \
	  | sort -n | uniq -c | awk '{printf "    value %-8s seen %2d times\n", $$2, $$1}'; \
	  echo; \
	  pkill -f 'uvicorn week_11_observability' >/dev/null 2>&1; \
	  echo "  The values add up to the true total, and not one of them IS it."; \
	  echo "  Prometheus would record a counter that repeatedly falls, and rate()"; \
	  echo "  reads every fall as a process restart."

## Just the Week 11 tests. No Docker, no services, no network.
test-observability:
	uv run pytest tests/test_metrics.py tests/test_slo.py \
	  tests/test_prometheus_rules.py tests/test_dashboard.py \
	  tests/test_traffic.py tests/test_scope.py -q

## The whole observability half, in order, assuming the pipeline has run.
obs: image
	$(MAKE) --no-print-directory up
	$(MAKE) --no-print-directory api-up
	$(MAKE) --no-print-directory traffic
	$(MAKE) --no-print-directory alerts-test
	$(MAKE) --no-print-directory slo-budget
	$(MAKE) --no-print-directory grafana
