.PHONY: up down down-v logs ps sync dvc-init data-v1 data-v2 dvc-add dvc-push \
        dvc-pull dvc-status dvc-roundtrip repro dag metrics link \
        runs-for-data register promote promote-champion trace all test test-fast \
        validate validate-broken validate-model-input predict predict-bad \
        data-gate-fail slices gate fairness baseline baseline-sync gate-fail \
        ratchet lint fmt-check ci ci-local ct-local ci-fail ci-explain \
        install-ci uninstall-ci test-unit test-data test-eval test-integration \
        ensure-env gate-summary ensure-data flow flow-dvc flow-retry \
        flow-committed serve prefect-ui test-flows

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
	    cp "$$f" "$$root/.github/workflows/week08-$$(basename $$f)"; \
	    echo "installed -> .github/workflows/week08-$$(basename $$f)"; \
	  done
	@echo "Commit and push to run them. \`make uninstall-ci\` removes them again."

uninstall-ci:
	@root=$$(git rev-parse --show-toplevel) && \
	  rm -f "$$root"/.github/workflows/week08-*.yml && echo "removed week08-*.yml"

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

## Exercise 4 -- the training flow as a scheduled run starts it: it refuses an
## uncommitted params.yaml.
flow-committed: ensure-env ensure-data
	uv run python src/main.py flow --require-committed

## Exercise 5 -- a scheduled deployment. Ctrl-C to stop.
serve: ensure-env ensure-data
	uv run python src/main.py serve --cron "$(or $(CRON),*/5 * * * *)"

## Open the Prefect UI.
prefect-ui:
	@echo "http://127.0.0.1:$${PREFECT_PORT:-5520}"

## Just the Week 8 tests.
test-flows:
	uv run pytest tests/test_flows.py tests/test_scope.py -q
