.PHONY: up down down-v logs ps sync data-v2 dvc-push dvc-pull dvc-status \
        validate predict repro dag metrics link gate baseline-sync register \
        promote promote-champion trace test test-fast test-unit test-data \
        test-eval lint ensure-data ensure-env ci ct-local gate-summary \
        install-ci uninstall-ci flow serve-mlflow serve-api bench image \
        run-image kind-up kind-down k8s-deploy k8s-status kserve-install \
        kserve-status model-publish model-publish-variant store-list \
        release-check isvc-deploy isvc-canary canary-shift isvc-status \
        isvc-url isvc-health split-measure loadtest smoke smoke-local _job \
        promote-canary rollback rollback-reapply metrics-show cardinality \
        api-up api-down logs-json traffic promql grafana prometheus-ui \
        dashboard-check slo-budget alerts-check alerts-test alerts-test-fail \
        alert-fire alert-noise prom-reload targets workers-trap \
        test-observability

# The commands of the training pipeline, the CI checks, serving, the rollout and the
# observability lab.
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
	    cp "$$f" "$$root/.github/workflows/week11-$$(basename $$f)"; \
	    echo "installed -> .github/workflows/week11-$$(basename $$f)"; \
	  done
	@echo "Commit and push to run them. \`make uninstall-ci\` removes them again."

uninstall-ci:
	@root=$$(git rev-parse --show-toplevel) && \
	  rm -f "$$root"/.github/workflows/week11-*.yml && echo "removed week11-*.yml"

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
	@cp params.yaml .params.yaml.w11-bak
	@if [ -n "$(FAMILY)" ]; then \
	  uv run python -c "import pathlib; p=pathlib.Path('params.yaml'); p.write_text(p.read_text().replace('  family: logreg', '  family: $(FAMILY)'))"; fi
	@if [ -n "$(C)" ]; then \
	  uv run python -c "import pathlib; p=pathlib.Path('params.yaml'); p.write_text(p.read_text().replace('  C: 1.0', '  C: $(C)'))"; fi
	-$(DVC) repro
	@set +e; $(MAKE) --no-print-directory model-publish VERSION=$(VERSION) FORCE=$(FORCE); rc=$$?; set -e; \
	  mv .params.yaml.w11-bak params.yaml; \
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

## Exercise 1 -- read the exposition format, in-process. FILTER= narrows it.
metrics-show: ensure-data
	@uv run python src/main.py metrics-show $(if $(FILTER),--filter '$(FILTER)',)

## Exercise 1 -- the cardinality experiment: route template vs raw path.
cardinality: ensure-data
	@uv run python src/main.py cardinality --requests $(or $(N),50)

## Exercise 2 -- start the API container (Compose profile `api`). Needs `make image` first.
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

## Exercise 4 -- stop it, and watch ServiceDown go pending -> firing.
api-down:
	docker compose --profile api stop api
	@echo
	@echo "  Now watch $(PROM_URL)/alerts"
	@echo "  ServiceDown goes pending within a scrape and firing one minute later."

## Exercise 2 -- one request, two shapes, side by side.
logs-json:
	@echo "=== the metric: all requests, aggregated ==="
	@curl -s $(API_URL)/metrics | grep '^http_requests_total' || \
	  { echo "  (the api container is not up -- make api-up)"; exit 1; }
	@echo
	@echo "=== the log: one line per request ==="
	@docker compose logs --no-log-prefix api 2>/dev/null \
	  | grep '"event": "http_request"' | tail -3 \
	  | (command -v jq >/dev/null && jq . || cat)

## Exercise 2 -- traffic with a known mix, e.g. make traffic N=600 RATE=30 MIX=valid=8,violation=1,notfound=1
traffic:
	@uv run python src/main.py traffic --url $(API_URL) \
	  --requests $(or $(N),300) --rate $(or $(RATE),20) \
	  $(if $(MIX),--mix '$(MIX)',) --seed $(or $(SEED),42)

## Exercise 2 -- the queries to paste into Prometheus.
promql:
	@echo
	@echo "  Open $(PROM_URL)/graph and paste these in turn."
	@echo
	@echo "  1. up{job=\"diabetes-api\"}"
	@echo "       1 or 0. Prometheus adds it on every scrape."
	@echo
	@echo "  2. http_requests_total"
	@echo "       The raw counter. Its value depends on when the process started."
	@echo
	@echo "  3. rate(http_requests_total[1m])"
	@echo "       Requests per second. A restart is handled as a reset."
	@echo "       The window must span at least two scrapes."
	@echo
	@echo "  4. sum by (status) (rate(http_requests_total[1m]))"
	@echo "       'sum by' keeps only the labels you name."
	@echo
	@echo "  5. sum(rate(http_requests_total{status=~\"5..\"}[5m]))"
	@echo "     / sum(rate(http_requests_total[5m]))"
	@echo "       The availability SLI: a ratio of requests, not uptime."
	@echo
	@echo "  6. histogram_quantile(0.95,"
	@echo "       sum by (le) (rate(http_request_duration_seconds_bucket[5m])))"
	@echo "       p95: rate the buckets, sum by le, then take the quantile."
	@echo
	@echo "  7. sum by (check) (rate(model_contract_violations_total[5m]))"
	@echo "       Contract violations per second, by check."
	@echo

## Exercise 3 -- the dashboard, and the URLs.
grafana:
	@echo
	@echo "  $(GRAF_URL)          (anonymous Editor access -- a lab convenience)"
	@echo "  $(GRAF_URL)/d/diabetes-service"
	@echo
	@echo "  Provisioned from grafana/. Grafana does not save a UI edit: copy the"
	@echo "  dashboard JSON into grafana/dashboards/diabetes-service.json, and"
	@echo "  Grafana reloads the file within 10s."
	@echo "  Every panel has a note in its description; hover the (i)."
	@echo

## The Prometheus pages.
prometheus-ui:
	@echo "  $(PROM_URL)/graph     PromQL"
	@echo "  $(PROM_URL)/targets   who is being scraped, and is it working"
	@echo "  $(PROM_URL)/alerts    inactive / pending / firing"
	@echo "  $(PROM_URL)/rules     what is being evaluated, and when it last ran"

## Exercise 3 -- the dashboard tests: a renamed metric leaves a panel empty and fails here.
dashboard-check:
	uv run pytest tests/test_dashboard.py -q

## Exercise 4 -- the promise, the budget, and the burn-rate table.
slo-budget:
	@uv run python src/main.py slo-budget

## Check that prometheus.yml and the rules load, with promtool from the Prometheus image.
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

## The negative test: with ServiceDown's `for:` loosened to 5m, alerts-test must fail.
alerts-test-fail:
	@cp prometheus/rules/service.yml .service.yml.bak
	@uv run python -c "import pathlib; p=pathlib.Path('prometheus/rules/service.yml'); p.write_text(p.read_text().replace('        for: 1m', '        for: 5m', 1))"
	@echo 'Planted "for: 5m" on ServiceDown. The suite must now fail.'
	@set +e; $(MAKE) --no-print-directory alerts-test; rc=$$?; set -e; \
	  mv .service.yml.bak prometheus/rules/service.yml; \
	  echo; echo "promtool exit code: $$rc  (non-zero is the point)"; \
	  echo "service.yml restored."; \
	  test "$$rc" -ne 0 || { echo; \
	    echo "Unexpected: the rule tests passed with a broken rule."; \
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
	@echo "  The gap between pending and firing is the rule's 'for: 1m'."

## Not an exercise -- how often would each rule have woken somebody?
alert-noise:
	@uv run python src/main.py alert-noise --seed $(or $(SEED),42)

## Reload the rules without a restart.
prom-reload:
	@curl -s -X POST $(PROM_URL)/-/reload && echo "  reloaded" || \
	  echo "  reload failed -- is prometheus up, and was --web.enable-lifecycle set?"

## Who is being scraped, and is it working.
targets:
	@curl -s $(PROM_URL)/api/v1/targets | \
	  uv run python -c "import json,sys; [print(f\"  {t['labels']['job']:<16} {t['scrapeUrl']:<34} {t['health']:<8} {t.get('lastError','')}\") for t in json.load(sys.stdin)['data']['activeTargets']]"

## Four uvicorn workers, 30 scrapes of one counter: each worker keeps its own count.
workers-trap: ensure-data
	@echo "Starting uvicorn with four workers on 5599..."
	@uv run uvicorn week_11_observability.api:app --host 127.0.0.1 --port 5599 --workers 4 \
	  > /tmp/w11-workers.log 2>&1 & \
	  sleep 12; \
	  P='{"pregnancies":6,"glucose":148,"blood_pressure":72,"skin_thickness":35,"insulin":125,"bmi":33.6,"diabetes_pedigree":0.627,"age":50}'; \
	  for i in $$(seq $(or $(N),200)); do \
	    curl -s --no-keepalive -X POST localhost:5599/predict \
	      -H 'content-type: application/json' -d "$$P" > /dev/null; done; \
	  echo; echo "  $(or $(N),200) requests sent. Thirty scrapes of one counter:"; echo; \
	  for i in $$(seq 30); do \
	    curl -s --no-keepalive localhost:5599/metrics \
	    | grep '^http_requests_total{method="POST",route="/predict",status="200"}' \
	    | awk '{print $$2}'; done \
	  | sort -n | uniq -c | awk '{printf "    value %-8s seen %2d times\n", $$2, $$1}'; \
	  echo; \
	  pkill -f 'uvicorn week_11_observability' >/dev/null 2>&1; \
	  echo "  The values add up to the true total, and none of them is the total."

## The observability tests. No Docker, no services, no network.
test-observability:
	uv run pytest tests/test_metrics.py tests/test_slo.py \
	  tests/test_prometheus_rules.py tests/test_dashboard.py \
	  tests/test_traffic.py tests/test_scope.py -q
