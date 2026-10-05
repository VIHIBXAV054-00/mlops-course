.PHONY: up down down-v logs ps sync run sweep best register promote trace rollback query all test test-fast

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

## Exercises 1-2 — one fully-logged run (params, metrics, tags, plots, model)
run:
	uv run python src/main.py run

## Exercise 3 — parameter sweep: one parent run with six children
sweep:
	uv run python src/main.py sweep

## Exercise 4 — server-side search over the latest sweep   (make best METRIC=roc_auc)
best:
	uv run python src/main.py best $(if $(METRIC),--metric $(METRIC))

## Exercise 5 — register the run you chose (a new version)   (make register RUN_ID=<id>)
register:
	uv run python src/main.py register $(if $(RUN_ID),--run-id $(RUN_ID))

## Exercise 6 — promote a version to @staging and @champion  (make promote VERSION=2 REASON="...")
promote:
	uv run python src/main.py promote $(if $(VERSION),--version $(VERSION)) $(if $(REASON),--reason "$(REASON)")

## Exercise 6 — traceability check: alias -> version -> run -> params -> commit
trace:
	uv run python src/main.py trace

## Exercise 7 — move both aliases back                       (make rollback VERSION=1 REASON="...")
rollback:
	uv run python src/main.py rollback $(if $(VERSION),--version $(VERSION)) $(if $(REASON),--reason "$(REASON)")

## Stretch — any search_runs filter                          (make query FILTER="..." ORDER_BY="...")
query:
	uv run python src/main.py query --filter "$(FILTER)" $(if $(ORDER_BY),--order-by "$(ORDER_BY)")

## Exercises 1-6 end to end
all:
	uv run python src/main.py all

## Run every test (live tests auto-skip when the stack is down)
test:
	uv run pytest tests/ -v

## Run only the tests that do not need the stack
test-fast:
	uv run pytest tests/ -v -m "not live"
