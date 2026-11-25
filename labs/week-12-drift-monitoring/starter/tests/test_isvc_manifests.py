"""The InferenceService manifests, checked as data: the base and the canary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit

K8S = Path(__file__).resolve().parents[1] / "k8s"

BASE = K8S / "inferenceservice.yaml"
CANARY = K8S / "inferenceservice-canary.yaml"

# real KServe fields this lab does not use
OUT_OF_SCOPE_FIELDS = {
    "maxReplicas",
    "scaleTarget",
    "scaleMetric",
    "transformer",
    "explainer",
    "batcher",
    "logger",
}


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        pytest.skip(f"{path.name} is missing: restore it with `git checkout k8s/{path.name}`.")
    return yaml.safe_load(path.read_text())


@pytest.fixture(scope="module")
def base() -> dict[str, Any]:
    return _load(BASE)


@pytest.fixture(scope="module")
def canary() -> dict[str, Any]:
    return _load(CANARY)


def _predictor(isvc: dict[str, Any]) -> dict[str, Any]:
    return isvc["spec"]["predictor"]


def _container(isvc: dict[str, Any]) -> dict[str, Any]:
    return _predictor(isvc)["containers"][0]


def _env(isvc: dict[str, Any]) -> dict[str, str]:
    return {entry["name"]: entry["value"] for entry in _container(isvc).get("env", [])}


def test_both_manifests_are_inferenceservices(base, canary):
    for isvc in (base, canary):
        assert isvc["apiVersion"] == "serving.kserve.io/v1beta1"
        assert isvc["kind"] == "InferenceService"
        assert isvc["metadata"]["name"] == "diabetes"


def test_the_user_container_is_named_kserve_container(base, canary):
    """KServe finds the container by this name. Any other name leaves /mnt/models empty."""
    for isvc in (base, canary):
        assert _container(isvc)["name"] == "kserve-container"


def test_the_model_is_fetched_not_baked(base, canary):
    """The `STORAGE_URI` env var makes KServe mount the model into a custom container."""
    for isvc in (base, canary):
        env = _env(isvc)
        assert env["STORAGE_URI"].startswith("pvc://"), (
            "the model must come from the store at startup"
        )
        assert env["MODEL_PATH"].startswith("/mnt/models"), (
            "KServe mounts the model at /mnt/models; MODEL_PATH has to point there"
        )


def test_the_canary_differs_from_the_base_in_exactly_two_places(base, canary):
    """A canary tests one change, the model: only STORAGE_URI and the percentage differ."""
    assert _container(base)["image"] == _container(canary)["image"], (
        "keep the base image: only the model may change between revisions"
    )

    base_env, canary_env = _env(base), _env(canary)
    assert base_env["STORAGE_URI"] != canary_env["STORAGE_URI"], (
        "a canary that serves the same model version is not a canary"
    )
    assert {k: v for k, v in base_env.items() if k != "STORAGE_URI"} == {
        k: v for k, v in canary_env.items() if k != "STORAGE_URI"
    }

    base_predictor = {k: v for k, v in _predictor(base).items() if k != "containers"}
    canary_predictor = {
        k: v
        for k, v in _predictor(canary).items()
        if k not in {"containers", "canaryTrafficPercent"}
    }
    assert base_predictor == canary_predictor

    base_container = {k: v for k, v in _container(base).items() if k != "env"}
    canary_container = {k: v for k, v in _container(canary).items() if k != "env"}
    assert base_container == canary_container


def test_only_the_canary_declares_a_traffic_split(base, canary):
    """The base manifest is also the rollback, so it must not declare a split.

    `canaryTrafficPercent` absent means "the latest revision takes everything".
    Re-applying this file is therefore one way to roll back.
    """
    assert "canaryTrafficPercent" not in _predictor(base)
    percent = _predictor(canary)["canaryTrafficPercent"]
    assert isinstance(percent, int)
    assert 0 <= percent <= 100, "a percentage outside [0, 100] is rejected by the webhook"
    assert percent < 50, (
        "a canary takes a small share of traffic. Over half is a full deploy."
    )


def test_tag_routing_is_enabled_so_a_revision_can_be_addressed_directly(base, canary):
    """With tags, each revision has its own hostname, so the smoke test can target the canary."""
    for isvc in (base, canary):
        annotations = isvc["metadata"].get("annotations", {})
        assert annotations.get("serving.kserve.io/enable-tag-routing") == "true"


def test_the_probe_still_asks_the_app_a_question(base, canary):
    """The readiness probe proves only that the model loaded, which is why `make smoke` exists."""
    for isvc in (base, canary):
        probe = _container(isvc)["readinessProbe"]["httpGet"]
        assert probe["path"] == "/health"
        assert probe["port"] == _container(isvc)["ports"][0]["containerPort"]


def test_no_out_of_scope_fields_have_crept_in(base, canary):
    """Checked on the parsed documents, so a comment cannot trip it."""
    def walk(node: Any) -> list[str]:
        found = []
        if isinstance(node, dict):
            for key, value in node.items():
                if key in OUT_OF_SCOPE_FIELDS:
                    found.append(key)
                found += walk(value)
        elif isinstance(node, list):
            for item in node:
                found += walk(item)
        return found

    for isvc in (base, canary):
        assert not walk(isvc), (
            f"out-of-scope fields in {isvc['metadata']['name']}: {walk(isvc)} — "
            "autoscaling, transformers and explainers are later material"
        )


def test_the_store_is_a_read_only_volume_the_node_actually_has(base):
    """The kind config, the PV and the PVC line up. A mismatch gives an empty /mnt/models, not an error.

    Without `storageClassName: ""`, kind provisions a new empty volume instead.
    """
    docs = list(yaml.safe_load_all((K8S / "model-store.yaml").read_text()))
    pv = next(d for d in docs if d["kind"] == "PersistentVolume")
    pvc = next(d for d in docs if d["kind"] == "PersistentVolumeClaim")

    assert pv["spec"]["storageClassName"] == ""
    assert pvc["spec"]["storageClassName"] == ""
    assert pvc["spec"]["volumeName"] == pv["metadata"]["name"]
    assert "ReadOnlyMany" in pv["spec"]["accessModes"]

    kind_config = yaml.safe_load((K8S / "kind-cluster.yaml").read_text())
    mounts = kind_config["nodes"][0]["extraMounts"]
    assert any(m["containerPath"] == pv["spec"]["hostPath"]["path"] for m in mounts), (
        "the PV points at a path inside the node that kind never mounted — "
        "/mnt/models would be empty and the pod would never become ready"
    )

    claim = pvc["metadata"]["name"]
    assert _env(base)["STORAGE_URI"].startswith(f"pvc://{claim}/"), (
        "STORAGE_URI names the claim, and a typo leaves the pod stuck at startup"
    )


def test_the_measurement_job_runs_the_services_own_image(base):
    """The load generator runs from the serving image, so you measure the code you ship."""
    job = yaml.safe_load((K8S / "job.yaml").read_text())
    assert job["kind"] == "Job"
    spec = job["spec"]["template"]["spec"]
    assert spec["containers"][0]["image"] == _container(base)["image"]
    assert job["spec"]["backoffLimit"] == 0, (
        "a retried measurement averages away the thing being measured"
    )
    annotations = job["spec"]["template"]["metadata"]["annotations"]
    assert annotations["sidecar.istio.io/inject"] == "false", (
        "an extra proxy in the path adds latency that belongs to the instrument"
    )
