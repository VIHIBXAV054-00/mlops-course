.PHONY: up down down-v logs ps sync data-v2 dvc-push dvc-pull dvc-status \
        validate predict repro dag metrics link gate baseline-sync register \
        promote promote-champion trace test test-fast test-unit test-data \
        test-eval lint ensure-data ensure-env ci ct-local gate-summary \
        install-ci uninstall-ci flow serve-mlflow serve-api bench image \
        run-image kind-up kind-down k8s-deploy k8s-status kserve-install \
        kserve-status model-publish model-publish-variant store-list \
        release-check isvc-deploy isvc-canary canary-shift isvc-status \
        isvc-url isvc-health split-measure loadtest smoke smoke-local _job \
        promote-canary rollback rollback-reapply metrics-show api-up api-down \
        traffic slo-budget alerts-test prom-reload targets predictions-on \
        predictions-off request api-logs predictions-head traffic-drift \
        drift-report drift-insufficient drift-open drift-policy \
        drift-sample-size drift-impact drift-vs-contract drift-metrics \
        drift-alerts-test drift-alerts-test-fail drift-stale drift-protocol \
        retrain-trigger test-drift

# The commands of the training pipeline, the CI checks, serving, the rollout, observability
# and the drift lab.
# The README's "Make targets" table lists the ones this lab uses.

# .env is sourced by the shell, so quoting and comments work as in a terminal.
# DVC reads the AWS_* names, so the Silo credentials from .env are mapped onto them.
DOTENV = set -a && . ./.env && set +a
DVC    = $(DOTENV) && AWS_ACCESS_KEY_ID="$$S3_ACCESS_KEY" \
                      AWS_SECRET_ACCESS_KEY="$$S3_SECRET_KEY" \
                      DVC_PAGER=cat uv run dvc

# ── The Compose stack ────────────────────────────────────────────────────────

up:
	docker compose up -d --wait

## Stop the services; the data stays in the volumes.
down:
	docker compose down

## Stop the services and delete the volumes.
down-v:
	docker compose down -v

logs:
	docker compose logs -f

ps:
	docker compose ps

sync:
	uv sync --all-groups

# ── Data and DVC ─────────────────────────────────────────────────────────────

## Build dataset version 2: both batches. The pipeline uses this one.
data-v2:
	uv run python src/main.py build-data --version 2

dvc-push:
	$(DVC) push

dvc-pull:
	$(DVC) pull

## Compare the workspace, the cache and the remote.
dvc-status:
	$(DVC) status
	$(DVC) status --cloud

# ── Data contracts ───────────────────────────────────────────────────────────

## Check the data against the ingestion contract. Exits 1 when the data fails.
validate:
	uv run python src/main.py validate

## Check one request against the contract, then score it.
predict:
	uv run python src/main.py predict --payload example

# ── Pipeline, gate and registry ──────────────────────────────────────────────

## Run the pipeline: validate, prepare, train, evaluate, gate. Only stale stages run.
repro:
	$(DVC) repro

dag:
	$(DVC) dag
	@echo "--- as mermaid ---"
	$(DVC) dag --mermaid

metrics:
	$(DVC) metrics show

## Force a new training run, so MLflow gets a new run with its metrics.
link:
	$(DVC) repro -f -s train
	$(DVC) repro -f -s evaluate
	$(DVC) repro

## The release decision. Exits 1 on a NO-GO and writes the report either way.
gate:
	uv run python src/main.py gate

## Copy the champion's metrics into the baseline, which raises the bar.
baseline-sync:
	uv run python src/main.py baseline-sync

## Register the model. Refuses unless reports/gate.json records a GO.
register:
	uv run python src/main.py register

## Move the staging alias. Refuses without a GO.
promote:
	uv run python src/main.py promote

## Move the staging and champion aliases.
promote-champion:
	uv run python src/main.py promote --champion

## Follow the chain from the champion alias to the run, the data and the gate verdict.
trace:
	uv run python src/main.py trace

# ── Tests and CI ─────────────────────────────────────────────────────────────

## Every test. Tests that need the stack or a DVC repo skip themselves without it.
test:
	uv run pytest tests/ -v

## The tests that need neither the stack nor a DVC repo.
test-fast:
	uv run pytest tests/ -v -m "not live and not dvc"

test-unit:
	uv run pytest tests/ -q -m "unit"

test-data:
	uv run pytest tests/ -q -m "data and not live and not dvc"

test-eval:
	uv run pytest tests/ -q -m "eval and not live and not dvc"

lint:
	uv run ruff check src tests

## Stop with a hint when the DVC-tracked dataset is missing, as on a fresh clone.
ensure-data:
	@test -f data/measurements.csv || { \
	  echo "data/measurements.csv is missing -- it is DVC-tracked, so a fresh"; \
	  echo "clone does not have it. Rebuild it from the committed raw batches:"; \
	  echo "    make data-v2"; \
	  echo "(CI does exactly this, which is why it needs no object store.)"; \
	  exit 1; }

## Copy .env.example to .env when there is no .env, as on a CI runner.
ensure-env:
	@test -f .env || { cp .env.example .env; \
	  echo "no .env found -> copied .env.example (defaults; no secrets in this lab)"; }

## What ci.yml runs: lint, the tests, the pipeline and the gate.
ci: ensure-env ensure-data lint test-fast repro gate
	@echo
	@echo "CI passed: lint, tests, pipeline, gate."

## What ct.yml runs: retrain and gate, without a code change.
ct-local: ensure-env ensure-data
	$(MAKE) --no-print-directory repro
	$(MAKE) --no-print-directory gate

## The gate verdict as markdown, for $GITHUB_STEP_SUMMARY.
gate-summary:
	@uv run python src/main.py gate-summary

## Copy the workflows to .github/workflows at the repository root, where GitHub runs them.
install-ci:
	@root=$$(git rev-parse --show-toplevel) && mkdir -p "$$root/.github/workflows" && \
	  for f in .github/workflows/*.yml; do \
	    cp "$$f" "$$root/.github/workflows/week12-$$(basename $$f)"; \
	    echo "installed -> .github/workflows/week12-$$(basename $$f)"; \
	  done
	@echo "Commit and push to run them. \`make uninstall-ci\` removes them again."

uninstall-ci:
	@root=$$(git rev-parse --show-toplevel) && \
	  rm -f "$$root"/.github/workflows/week12-*.yml && echo "removed week12-*.yml"

# ── Prefect flow ─────────────────────────────────────────────────────────────

## Run the training flow. Needs the stack: the CLI refuses without a Prefect server.
flow: ensure-env ensure-data
	uv run python src/main.py flow

# ── Serving ──────────────────────────────────────────────────────────────────

## MLflow's server for the champion, on port 5540.
## `--env-manager local` uses this Python instead of rebuilding the model's environment.
serve-mlflow: ensure-env
	$(DOTENV) && uv run mlflow models serve \
	  -m "models:/$${MLFLOW_REGISTERED_MODEL_NAME}@$${MLFLOW_CHAMPION_ALIAS:-champion}" \
	  --env-manager local -p 5540 --host 127.0.0.1

## Your service, on port 5541. It reads models/model.pkl, so it needs no stack.
serve-api: ensure-data
	uv run python src/main.py serve-api --port $(or $(PORT),5541)

## Batch and online scoring of the 192 test rows.
bench: ensure-data
	uv run python src/main.py bench

## Build the image with the model in it. Refuses unless the gate verdict is GO.
## With the stack up, the image records the champion's version; without it, "unknown".
image: ensure-env
	@set -e; \
	  eval "$$(uv run python src/main.py bake-info)"; \
	  echo "building: version=$$MODEL_VERSION run=$$RUN_ID gate=$$GATE_VERDICT source=$$MODEL_SOURCE"; \
	  test "$$GATE_VERDICT" = "GO" || { echo; \
	    echo "REFUSING to build: the recorded gate verdict is '$$GATE_VERDICT'."; \
	    echo "Only a model with a GO verdict may be released, and an image is a release."; \
	    exit 1; }; \
	  docker build --progress=plain -f serve.Dockerfile -t diabetes-api:local \
	    --build-arg MODEL_VERSION="$$MODEL_VERSION" --build-arg RUN_ID="$$RUN_ID" \
	    --build-arg GATE_VERDICT="$$GATE_VERDICT" --build-arg MODEL_SOURCE="$$MODEL_SOURCE" .

## Run the image on its own, on port 5542.
run-image:
	docker run --rm -p $(or $(PORT),5542):8000 --name diabetes-api diabetes-api:local

## Create or delete the local cluster. It mounts ./model-store into the node.
kind-up:
	kind create cluster --config k8s/kind-cluster.yaml
	kubectl cluster-info --context kind-mlops

kind-down:
	kind delete cluster --name mlops

## Copy the image onto the kind node, then apply the manifests.
k8s-deploy:
	kind load docker-image diabetes-api:local --name mlops
	kubectl apply -f k8s/deployment.yaml -f k8s/service.yaml
	kubectl rollout status deployment/diabetes-api --timeout=120s
	@echo
	@echo "  kubectl port-forward svc/diabetes-api 5543:80"
	@echo "  curl localhost:5543/health"

## The pods, and the pods behind the Service.
k8s-status:
	@kubectl get pods -l app=diabetes-api -o wide
	@echo
	@kubectl describe service diabetes-api | grep -E "^(Name|Selector|Endpoints):"

# ── KServe rollout ───────────────────────────────────────────────────────────

# The KServe installer, downloaded once into .kserve/ and checked against its hash.
KSERVE_VERSION  = v0.20.0
KSERVE_INSTALLER = kserve-knative-mode-full-install-with-manifests.sh
KSERVE_SHA256   = 3316776068a5d52ef74ce0dfe152f690102ba226ac8e67e9bb6fe8ebcfa39ff2
KSERVE_URL      = https://github.com/kserve/kserve/releases/download/$(KSERVE_VERSION)/$(KSERVE_INSTALLER)

CLUSTER   = mlops
ISVC      = diabetes
# KServe's default host name. `make isvc-url` prints the real one.
ISVC_HOST = $(ISVC).default.example.com
GATEWAY   = http://127.0.0.1:5550
# The Jobs measure from inside the cluster, through this address.
ISVC_INTERNAL = http://$(ISVC)-predictor.default.svc.cluster.local

## Install cert-manager, Istio, Knative and KServe. About 5 minutes the first time.
kserve-install: .kserve/$(KSERVE_INSTALLER)
	@echo "==> installing KServe $(KSERVE_VERSION) (knative mode) into kind cluster '$(CLUSTER)'"
	@kubectl config use-context kind-$(CLUSTER) >/dev/null
	NO_COLOR=1 bash .kserve/$(KSERVE_INSTALLER)
	@echo
	@echo "==> exposing the ingress gateway on $(GATEWAY)"
	kubectl patch svc istio-ingressgateway -n istio-system \
	  -p '{"spec":{"ports":[{"name":"http2","port":80,"nodePort":30080}]}}'
	@$(MAKE) --no-print-directory kserve-status

## Download the installer once, and check its hash before running it.
.kserve/$(KSERVE_INSTALLER):
	@mkdir -p .kserve
	curl -sSL -o $@ $(KSERVE_URL)
	@echo "$(KSERVE_SHA256)  $@" | shasum -a 256 -c - || { \
	  echo "Checksum mismatch: not running it. Delete .kserve/ and retry."; rm -f $@; exit 1; }

## What is running, and which versions.
kserve-status:
	@for ns in cert-manager istio-system knative-serving kserve; do \
	  printf "  %-16s %s pod(s) ready\n" "$$ns" \
	    "$$(kubectl get pods -n $$ns --no-headers 2>/dev/null | grep -c ' Running ')"; \
	done
	@echo
	@kubectl get crd 2>/dev/null | grep -E 'inferenceservices|revisions.serving' | sed 's/^/  /'

# ── Model store ──────────────────────────────────────────────────────────────

## Publish the current model as VERSION (default v1). FORCE=1 publishes a NO-GO model.
model-publish: ensure-data
	uv run python src/main.py model-publish --store-version $(or $(VERSION),v1) \
	  $(if $(FORCE),--force,)

## Retrain with another FAMILY or C, publish the result, and restore params.yaml.
model-publish-variant: ensure-data
	@cp params.yaml .params.yaml.w12-bak
	@if [ -n "$(FAMILY)" ]; then \
	  uv run python -c "import pathlib; p=pathlib.Path('params.yaml'); p.write_text(p.read_text().replace('  family: logreg', '  family: $(FAMILY)'))"; fi
	@if [ -n "$(C)" ]; then \
	  uv run python -c "import pathlib; p=pathlib.Path('params.yaml'); p.write_text(p.read_text().replace('  C: 1.0', '  C: $(C)'))"; fi
	-$(DVC) repro
	@set +e; $(MAKE) --no-print-directory model-publish VERSION=$(VERSION) FORCE=$(FORCE); rc=$$?; set -e; \
	  mv .params.yaml.w12-bak params.yaml; \
	  echo "params.yaml restored."; \
	  $(DVC) repro >/dev/null 2>&1 || true; \
	  test "$$rc" -eq 0 || { echo "publish refused (exit $$rc)."; exit $$rc; }

## The store's versions and their gate verdicts.
store-list:
	uv run python src/main.py store-list

# ── Rollout plan ─────────────────────────────────────────────────────────────

## Is release.yaml complete?
release-check:
	@uv run python src/main.py release-check

RELEASE = uv run --quiet python src/main.py release-value --key

# ── InferenceService ─────────────────────────────────────────────────────────

## Load the image into kind, create the store volume, apply the InferenceService.
isvc-deploy:
	kind load docker-image diabetes-api:local --name $(CLUSTER)
	kubectl apply -f k8s/model-store.yaml
	kubectl apply -f k8s/inferenceservice.yaml
	kubectl wait --for=condition=Ready inferenceservice/$(ISVC) --timeout=300s
	@$(MAKE) --no-print-directory isvc-url

## Apply the canary manifest at 0%. VERSION defaults to model.candidate in release.yaml.
isvc-canary:
	sed -e "s|pvc://diabetes-models/[A-Za-z0-9]*|pvc://diabetes-models/$(or $(VERSION),$$($(RELEASE) model.candidate))|" \
	  -e 's|canaryTrafficPercent: *[0-9]*|canaryTrafficPercent: 0|' \
	  k8s/inferenceservice-canary.yaml | kubectl apply -f -
	kubectl wait --for=condition=Ready inferenceservice/$(ISVC) --timeout=300s
	@$(MAKE) --no-print-directory isvc-status

## Smoke-test the newest revision, then set the canary percentage. FORCE=1 skips the test.
canary-shift:
	@if [ -z "$(FORCE)" ]; then \
	  $(MAKE) --no-print-directory smoke VERSION=$(or $(VERSION),$$($(RELEASE) model.candidate)) || \
	  { echo; echo "  Stopped: the smoke test failed, the canary keeps 0%."; exit 1; }; fi
	kubectl patch isvc $(ISVC) --type merge \
	  -p "{\"spec\": {\"predictor\": {\"canaryTrafficPercent\": $$($(RELEASE) canary.percent)}}}"
	@sleep 5
	@$(MAKE) --no-print-directory isvc-status

## The revisions, the pods and the traffic split.
isvc-status:
	@echo
	@kubectl get isvc $(ISVC)
	@echo
	@kubectl get revision -l serving.knative.dev/service=$(ISVC)-predictor
	@echo
	@kubectl get pods -l serving.knative.dev/service=$(ISVC)-predictor
	@echo
	@echo "  traffic split:"
	@kubectl get isvc $(ISVC) -o jsonpath='{range .status.components.predictor.traffic[*]}    {.revisionName} {.percent}%{"\t"}tag={.tag}{"\n"}{end}'

## The URLs, and how to reach the service from the laptop.
isvc-url:
	@echo
	@echo "  external : $$(kubectl get isvc $(ISVC) -o jsonpath='{.status.url}')"
	@echo "  internal : $$(kubectl get isvc $(ISVC) -o jsonpath='{.status.address.url}')"
	@echo
	@echo "  The hostname is not in DNS, so send the Host header to the gateway:"
	@echo "    curl -s -H 'Host: $(ISVC_HOST)' $(GATEWAY)/health"
	@echo

## /health through the gateway.
isvc-health:
	@curl -s -H "Host: $(ISVC_HOST)" $(GATEWAY)/health

# ── Tests in the cluster ─────────────────────────────────────────────────────

## Count which revision answered N requests.
split-measure:
	@$(MAKE) --no-print-directory _job JOB=split-measure \
	  ARGS="split-measure --url $(ISVC_INTERNAL) --requests $(or $(N),200) --declared $$($(RELEASE) canary.percent)"

## The load test, at rising concurrency, against the limits in release.yaml.
LEVELS ?= 1,4,16,64
loadtest:
	@$(MAKE) --no-print-directory _job JOB=loadtest \
	  ARGS="loadtest --url $(ISVC_INTERNAL) --requests $(or $(N),200) --concurrency-levels $(LEVELS) --max-p95-ms $$($(RELEASE) load.max_p95_ms) --max-error-rate $$($(RELEASE) load.max_error_rate)"

## Smoke-test the newest revision through its own address.
smoke:
	@$(MAKE) --no-print-directory _job JOB=smoke \
	  ARGS="smoke --url http://latest-$(ISVC)-predictor.default.svc.cluster.local $(if $(VERSION),--store-version $(VERSION),) --min-spread $$($(RELEASE) smoke.min_probability_spread)"

## The same smoke test on the laptop, against a store version. No cluster needed.
smoke-local:
	MODEL_PATH=$(PWD)/model-store/$(or $(VERSION),v1)/model.pkl \
	  uv run python src/main.py smoke --store-version $(or $(VERSION),v1) \
	  --min-spread $$($(RELEASE) smoke.min_probability_spread)

## Run a command as a Job in the cluster, print its log and exit with its result.
_job:
	-@kubectl delete job w12-$(JOB) --ignore-not-found >/dev/null 2>&1
	@args=$$(printf '"%s", ' $(ARGS) | sed 's/, $$//'); \
	  sed -e 's|__NAME__|w12-$(JOB)|' -e "s|__ARGS__|$$args|" k8s/job.yaml \
	  | kubectl apply -f - >/dev/null
	@ok=""; for _ in $$(seq 1 150); do \
	  s=$$(kubectl get job w12-$(JOB) -o jsonpath='{.status.succeeded}' 2>/dev/null); \
	  f=$$(kubectl get job w12-$(JOB) -o jsonpath='{.status.failed}' 2>/dev/null); \
	  if [ -n "$$s" ]; then ok=yes; break; fi; \
	  if [ -n "$$f" ]; then ok=no; break; fi; \
	  sleep 2; done; \
	  kubectl logs job/w12-$(JOB) 2>/dev/null; \
	  kubectl delete job w12-$(JOB) --ignore-not-found >/dev/null; \
	  test "$$ok" = "yes" || { echo; \
	    echo "  $(JOB) failed in the cluster."; exit 1; }

# ── Promote and roll back ────────────────────────────────────────────────────

## Promote: the newest revision takes 100%.
promote-canary:
	kubectl patch isvc $(ISVC) --type json \
	  -p '[{"op": "remove", "path": "/spec/predictor/canaryTrafficPercent"}]'
	@sleep 5
	@$(MAKE) --no-print-directory isvc-status

## Roll back: the canary percentage goes to 0.
rollback:
	kubectl patch isvc $(ISVC) --type merge \
	  -p '{"spec": {"predictor": {"canaryTrafficPercent": 0}}}'
	@sleep 5
	@$(MAKE) --no-print-directory isvc-status

## Apply the base manifest again: a new revision that serves v1.
rollback-reapply:
	kubectl apply -f k8s/inferenceservice.yaml
	@sleep 5
	@$(MAKE) --no-print-directory isvc-status

# ── Observability ────────────────────────────────────────────────────────────

PROM_URL  = http://127.0.0.1:$(or $(PROMETHEUS_PORT),5560)
GRAF_URL  = http://127.0.0.1:$(or $(GRAFANA_PORT),5561)
API_URL   = http://127.0.0.1:$(or $(API_PORT),5562)

## The /metrics page, in-process after five requests. FILTER= narrows it.
metrics-show: ensure-data
	@uv run python src/main.py metrics-show $(if $(FILTER),--filter '$(FILTER)',)

## Start the API container (Compose profile `api`). Needs `make image` first.
api-up:
	@docker image inspect diabetes-api:local >/dev/null 2>&1 || { \
	  echo "diabetes-api:local does not exist yet."; \
	  echo "Build it first:  make image"; \
	  exit 1; }
	docker compose --profile api up -d --wait api
	@echo
	@echo "  api        $(API_URL)/health"
	@echo "  prometheus $(PROM_URL)/targets"
	@echo "  grafana    $(GRAF_URL)"

## Stop the API, and watch ServiceDown go pending -> firing.
api-down:
	docker compose --profile api stop api
	@echo
	@echo "  Now watch $(PROM_URL)/alerts"
	@echo "  ServiceDown goes pending within a scrape and firing one minute later."

## Traffic with a known mix, e.g. make traffic N=600 RATE=30 MIX=valid=8,violation=1,notfound=1
traffic:
	@uv run python src/main.py traffic --url $(API_URL) \
	  --requests $(or $(N),300) --rate $(or $(RATE),20) \
	  $(if $(MIX),--mix '$(MIX)',) --seed $(or $(SEED),42)

## The SLO, the error budget and the burn-rate table.
slo-budget:
	@uv run python src/main.py slo-budget

## Run the promtool tests in prometheus/tests/alerts_test.yml.
##
## `promtool test rules` runs the real rules against synthetic series and
## checks which alerts fire at which times. No server, no clock.
alerts-test:
	docker compose run --rm --no-deps --entrypoint promtool prometheus \
	  test rules /etc/prometheus/tests/alerts_test.yml

## Reload the rules without a restart.
prom-reload:
	@curl -s -X POST $(PROM_URL)/-/reload && echo "  reloaded" || \
	  echo "  reload failed -- is prometheus up, and was --web.enable-lifecycle set?"

## Who is being scraped, and is it working.
targets:
	@curl -s $(PROM_URL)/api/v1/targets | \
	  uv run python -c "import json,sys; [print(f\"  {t['labels']['job']:<16} {t['scrapeUrl']:<34} {t['health']:<8} {t.get('lastError','')}\") for t in json.load(sys.stdin)['data']['activeTargets']]"

# ── Drift monitoring ─────────────────────────────────────────────────────────

PRED_LOG = predictions/predictions.jsonl
DRIFT_REPORT = reports/drift.json

## Exercise 1 -- turn the prediction log on in .env.
predictions-on:
	@mkdir -p predictions
	@grep -q '^PREDICTION_LOG_PATH=' .env 2>/dev/null \
	  && sed -i.bak 's|^PREDICTION_LOG_PATH=.*|PREDICTION_LOG_PATH=$(PRED_LOG)|' .env \
	  || printf 'PREDICTION_LOG_PATH=%s\n' '$(PRED_LOG)' >> .env
	@rm -f .env.bak
	@echo
	@echo "  PREDICTION_LOG_PATH=$(PRED_LOG)"
	@echo
	@echo "  The log holds eight clinical measurements per person. .gitignore keeps"
	@echo "  it out of Git."
	@echo
	@echo "  Restart the service so it re-reads the environment:"
	@echo "    make serve-api        (host, port 5541)"
	@echo "    make api-down api-up  (container, port 5562)"
	@echo

## Turn the prediction log off. The rows already on disk stay.
predictions-off:
	@sed -i.bak '/^PREDICTION_LOG_PATH=/d' .env 2>/dev/null || true
	@rm -f .env.bak
	@echo "  PREDICTION_LOG_PATH removed from .env. The service will write nothing."
	@echo "  The rows already on disk are still there: \`rm $(PRED_LOG)\` if you mean it."

## Exercise 1 -- one request to the API. ZERO=glucose sends an impossible zero, which gets a 422.
request:
	@body=$$(python3 -c "import json; p={'pregnancies':6,'glucose':148,'blood_pressure':72,'skin_thickness':35,'insulin':125,'bmi':33.6,'diabetes_pedigree':0.627,'age':50}; z='$(ZERO)'; p.update({z: 0} if z else {}); print(json.dumps(p))"); \
	curl -s -i -X POST $(API_URL)/predict -H 'Content-Type: application/json' -d "$$body" \
	  | grep -iE '^HTTP|^x-request-id|^\{'; echo

## Exercise 1 -- the last N lines of the request log (default 10).
api-logs:
	@docker compose logs --no-log-prefix api | grep '"event": "http_request"' | tail -$(or $(N),10)

## Exercise 1 -- the last rows of the prediction log.
predictions-head:
	@uv run python src/main.py predictions-head $(if $(N),--requests $(N),)

## Exercise 1 -- 800 requests from a real cohort. COHORT=reference|drifted (default drifted).
traffic-drift:
	@uv run python src/main.py traffic --url $(API_URL) \
	  --requests $(or $(N),800) --rate $(or $(RATE),40) \
	  --cohort $(or $(COHORT),drifted) --seed $(or $(SEED),42)

## Exercise 2 -- the drift report: two windows in, a verdict out.
## Reads the prediction log, or a committed batch with COHORT= and N=.
## REFERENCE=pinned|unfiltered|small|log picks the reference. IMPACT=1 also scores the model.
drift-report:
	@uv run python src/main.py drift-report \
	  $(if $(COHORT),--cohort $(COHORT),) $(if $(N),--requests $(N),) \
	  $(if $(REFERENCE),--reference $(REFERENCE),) \
	  $(if $(IMPACT),--impact,) --seed $(or $(SEED),42)

## Exercise 3 -- the drift report with 300 rows, below min_samples.
drift-insufficient:
	@uv run python src/main.py drift-report --cohort drifted --requests 300

## Exercise 2 -- open Evidently's HTML report.
drift-open:
	@test -f reports/drift.html || { \
	  echo "  reports/drift.html does not exist yet. Run \`make drift-report\` first."; \
	  exit 1; }
	@echo "  reports/drift.html"
	@python3 -c "import webbrowser,pathlib;webbrowser.open(pathlib.Path('reports/drift.html').resolve().as_uri())" 2>/dev/null \
	  || echo "  (open it yourself)"

## Exercise 3 -- the policy, parsed, with every threshold and its direction.
drift-policy:
	@uv run python src/main.py drift-policy

## Exercise 3 -- a p-value and an effect size at four window sizes.
drift-sample-size:
	@uv run python src/main.py drift-sample-size --seed $(or $(SEED),42)

## Exercise 4 -- the model on both labelled windows.
drift-impact:
	@uv run python src/main.py drift-impact

## Exercise 4 -- the ingestion contract and the drift report on the drifted batch.
drift-vs-contract:
	@echo "=== the ingestion contract, against the drifted batch ==="
	@echo
	@uv run python src/main.py check-file --path data/raw/batch_02_new_arrival.csv
	@echo
	@echo "=== and the drift verdict on the same rows ==="
	@echo
	@$(MAKE) --no-print-directory drift-report COHORT=drifted N=720 \
	  | grep -E "VERDICT|glucose|ACTION" || true

## Provided -- the drift metrics on the API container's /metrics.
drift-metrics:
	@curl -s $(API_URL)/metrics | grep '^model_drift\|^model_reference' \
	  || { echo "  (the api container is not up -- make api-up)"; exit 1; }
	@echo
	@echo "  Read from $(DRIFT_REPORT) at scrape time."

## Provided -- promtool over the drift rules.
drift-alerts-test:
	docker compose run --rm --no-deps --entrypoint promtool prometheus \
	  check rules /etc/prometheus/rules/drift.yml
	docker compose run --rm --no-deps --entrypoint promtool prometheus \
	  test rules /etc/prometheus/tests/alerts_test.yml

## Provided -- set FeatureDriftDetected's `for:` to 6h: the alert tests must now fail.
drift-alerts-test-fail:
	@cp prometheus/rules/drift.yml .drift.yml.bak
	@uv run python -c "import pathlib; p=pathlib.Path('prometheus/rules/drift.yml'); p.write_text(p.read_text().replace('        for: 1h', '        for: 6h', 1))"
	@echo 'Planted "for: 6h" on FeatureDriftDetected. The suite must now fail.'
	@set +e; docker compose run --rm --no-deps --entrypoint promtool prometheus \
	  test rules /etc/prometheus/tests/alerts_test.yml; rc=$$?; set -e; \
	  mv .drift.yml.bak prometheus/rules/drift.yml; \
	  echo; echo "promtool exit code: $$rc  (expected: non-zero)"; \
	  echo "drift.yml restored."; \
	  test "$$rc" -ne 0 || { echo; \
	    echo "UNEXPECTED: the rule tests passed with a broken rule."; \
	    exit 1; }

## Provided -- age the drift report by 27 hours and watch DriftReportStale fire.
drift-stale:
	@test -f $(DRIFT_REPORT) || { echo "  run \`make drift-report\` first."; exit 1; }
	@cp $(DRIFT_REPORT) .drift.json.bak
	@echo "=== 1. ageing the report by 27 hours (max_age is 26h) ==="
	@uv run python -c "import json,pathlib,time; p=pathlib.Path('$(DRIFT_REPORT)'); r=json.loads(p.read_text()); r['computed_at']=time.time()-27*3600; p.write_text(json.dumps(r,indent=2,sort_keys=True))"
	@echo "    computed_at moved back. The verdict and the numbers are unchanged."
	@echo
	@echo "=== 2. what /metrics now says ==="
	@curl -s $(API_URL)/metrics | grep '^model_drift_report_timestamp_seconds' || true
	@echo
	@echo "=== 3. watch it change state (polling every 15s for 12 minutes, for: 10m) ==="
	@start=$$(date +%s); \
	 for _ in $$(seq 1 48); do \
	   state=$$(curl -s $(PROM_URL)/api/v1/rules | \
	     uv run python -c "import json,sys; print(next((r.get('state','-') for g in json.load(sys.stdin)['data']['groups'] for r in g['rules'] if r.get('name')=='DriftReportStale'), 'unknown'))" 2>/dev/null); \
	   printf "    +%4ds  DriftReportStale: %s\n" "$$(( $$(date +%s) - start ))" "$$state"; \
	   test "$$state" = "firing" && break; \
	   sleep 15; \
	 done
	@echo
	@echo "=== 4. put the report back ==="
	@mv .drift.json.bak $(DRIFT_REPORT)
	@echo "    restored. The alert resolves within a couple of evaluations."

## Provided -- the reaction protocol: what each verdict leads to.
drift-protocol:
	@uv run python src/main.py drift-protocol

## Provided -- drift report, policy, retraining flow and gate, in order.
## Works here only because the drifted batch has labels.
retrain-trigger:
	@echo "=== 1. is there drift? ==="
	@$(MAKE) --no-print-directory drift-report COHORT=drifted N=720 IMPACT=1 \
	  | grep -E "VERDICT|ACTION|·" || true
	@echo
	@verdict=$$(uv run python -c "import json;print(json.load(open('$(DRIFT_REPORT)'))['verdict'])"); \
	 severity=$$(uv run python -c "import json;print(json.load(open('$(DRIFT_REPORT)'))['severity'])"); \
	 echo "=== 2. what the policy says to do about a $$verdict ($$severity) ==="; \
	 if [ "$$verdict" = "NO_DRIFT" ] || [ "$$verdict" = "INSUFFICIENT" ]; then \
	   echo "    nothing. Stopping here is the correct outcome."; \
	   exit 0; \
	 fi; \
	 echo "    a ticket, or -- with measured degradation -- a page and a rollback."; \
	 echo "    Retraining is the last option, and only because this window has labels."
	@echo
	@echo "=== 3. retrain, and let the gate decide ==="
	@$(MAKE) --no-print-directory flow
	@echo
	@echo "=== 4. the gate decides ==="
	@uv run python src/main.py gate || true
	@echo
	@echo "  Nothing was registered, promoted or built."

## This week's tests. No Docker, no services, no network.
test-drift:
	uv run pytest tests/test_drift.py tests/test_drift_policy.py \
	  tests/test_drift_metrics.py tests/test_prediction_log.py \
	  tests/test_prometheus_rules.py tests/test_scope.py -q
