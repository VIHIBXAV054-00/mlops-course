# `grafana/` — the specification

Everything here is **provisioned from files**. You can change a dashboard in the Grafana UI, but the
change is kept only when you copy the dashboard JSON into the file. The argument is the one
`dvc.yaml`, `params.yaml` and the `InferenceService` manifest already made: **the thing that should
be argued about in a pull request has to be a file.** A dashboard saved only in Grafana's database is
not reviewable, not diffable, and lives in a volume somebody will delete.

```text
grafana/
  grafana.ini                     given — keeps the classic dashboard editor
  provisioning/
    datasources/prometheus.yml    given — read it, especially the two comments
    dashboards/provider.yml       given
  dashboards/
    diabetes-service.json         nine panels given, one to add in the UI   (Exercise 3)
```

## The two settings that do all the work

**A pinned datasource `uid`.** Grafana generates one when you add a datasource by hand, so a
dashboard exported from your machine points at a uid that exists nowhere else — and every panel comes
up **silently empty** for everybody except you. `tests/test_dashboard.py` asserts every panel's uid
matches the provisioned one.

**`allowUiUpdates: false`.** With it `true`, a UI edit is saved to Grafana's database and then
overwritten at the next rescan: a change that appears to work and then vanishes, which is the worst
possible way to find out where the source of truth is. With it `false`, Grafana refuses to save a UI
edit and offers the dashboard JSON, which you copy into the file.

(`access: proxy` matters too. It means Grafana's *server* queries Prometheus, so `http://prometheus:9090`
resolves on the Docker network. `access: direct` makes your *browser* query it, and your browser has
never heard of a host called `prometheus` — a failure that works fine for you and for nobody else.)

## Exercise 3 — the "Predictions by outcome" panel

Add the panel in the Grafana UI, as the lab README describes, and copy the dashboard JSON into
`dashboards/diabetes-service.json`. `tests/test_dashboard.py` then checks it like any other panel:

- its query names a metric the service exports, and a counter is wrapped in `rate()`;
- it uses the provisioned data source `uid`, `prometheus`;
- its `description` is longer than 60 characters. Grafana shows it on the (i) icon.

`grafana.ini` turns off Grafana 13's new dashboard layouts, so the JSON that Grafana offers when you
save has the same format as this file. In the save dialog, choose **Advanced options → Classic**
before you copy it.

## Then break it

Rename `http_requests_total` in `metrics.py`. The panels that use it would not show an error in
Grafana. They go empty, which looks the same as a service with no traffic.

`make dashboard-check` fails, because `tests/test_dashboard.py` checks every PromQL expression against
the metrics the application exports, read from a live registry.
