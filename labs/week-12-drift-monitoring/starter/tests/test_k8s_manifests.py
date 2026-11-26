"""The Deployment and Service manifests, checked as YAML without a cluster."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

K8S = Path(__file__).resolve().parents[1] / "k8s"


@pytest.fixture(scope="module")
def deployment() -> dict:
    path = K8S / "deployment.yaml"
    if not path.exists():
        pytest.skip("k8s/deployment.yaml is missing: restore it with `git checkout k8s/deployment.yaml`.")
    return yaml.safe_load(path.read_text())


@pytest.fixture(scope="module")
def service() -> dict:
    path = K8S / "service.yaml"
    if not path.exists():
        pytest.skip("k8s/service.yaml is missing: restore it with `git checkout k8s/service.yaml`.")
    return yaml.safe_load(path.read_text())


def test_the_manifests_are_the_kinds_they_claim(deployment, service):
    assert deployment["kind"] == "Deployment"
    assert service["kind"] == "Service"


def test_the_service_selector_matches_the_pod_labels(deployment, service):
    """A Service selects pods by label. A mismatch errors nowhere: the Service has no endpoints."""
    pod_labels = deployment["spec"]["template"]["metadata"]["labels"]
    selector = service["spec"]["selector"]
    assert selector.items() <= pod_labels.items(), (
        f"Service selector {selector} does not match pod labels {pod_labels} — "
        "the Service will have zero endpoints and port-forward will hang"
    )


def test_the_deployment_selector_matches_its_own_template(deployment):
    """Kubernetes rejects this one at apply time."""
    assert deployment["spec"]["selector"]["matchLabels"].items() <= (
        deployment["spec"]["template"]["metadata"]["labels"].items()
    )


def test_a_side_loaded_image_is_not_pulled(deployment):
    """An image loaded with `kind load docker-image` is in no registry, so it must not be pulled."""
    container = deployment["spec"]["template"]["spec"]["containers"][0]
    assert container.get("imagePullPolicy") == "IfNotPresent", (
        "a locally-built image side-loaded with `kind load docker-image` will "
        "sit in ErrImagePull unless imagePullPolicy is IfNotPresent"
    )


def test_both_probes_exist_and_point_at_a_real_route(deployment):
    """A probe on a route the app does not serve leaves the pod never ready."""
    from week_12_drift_monitoring.api import create_app

    routes = {getattr(r, "path", None) for r in create_app().routes}
    container = deployment["spec"]["template"]["spec"]["containers"][0]

    for probe in ("readinessProbe", "livenessProbe"):
        assert probe in container, f"{probe} missing"
        path = container[probe]["httpGet"]["path"]
        assert path in routes, f"{probe} probes {path}, which the app does not serve"


def test_liveness_is_slower_to_fire_than_readiness(deployment):
    """Readiness withholds traffic, liveness restarts the container, so liveness must wait longer."""
    container = deployment["spec"]["template"]["spec"]["containers"][0]
    ready, live = container["readinessProbe"], container["livenessProbe"]

    ready_budget = ready["initialDelaySeconds"] + ready["periodSeconds"] * ready["failureThreshold"]
    live_budget = live["initialDelaySeconds"] + live["periodSeconds"] * live["failureThreshold"]
    assert live_budget > ready_budget, (
        f"liveness fires after {live_budget}s but readiness after {ready_budget}s — "
        "the container will be killed before it is ever given a chance to become ready"
    )


def test_more_than_one_replica(deployment):
    """A rolling update needs somewhere to send traffic while a pod restarts."""
    assert deployment["spec"]["replicas"] >= 2


def test_the_container_port_is_named_and_referenced_by_name(deployment):
    """Named ports mean the number lives in exactly one place."""
    container = deployment["spec"]["template"]["spec"]["containers"][0]
    name = container["ports"][0]["name"]
    for probe in ("readinessProbe", "livenessProbe"):
        assert container[probe]["httpGet"]["port"] == name


def test_nothing_from_a_later_week_is_in_the_manifests():
    """The plain Deployment and Service use no Ingress, autoscaling or traffic split.

    The parsed documents are checked, not the text, so a comment cannot trip it.
    """
    forbidden_kinds = {"Ingress", "HorizontalPodAutoscaler", "InferenceService",
                       "VirtualService", "Gateway"}
    forbidden_keys = {"trafficPolicy", "canaryTrafficPercent", "autoscaling"}

    def keys(node):
        if isinstance(node, dict):
            for key, value in node.items():
                yield key
                yield from keys(value)
        elif isinstance(node, list):
            for item in node:
                yield from keys(item)

    # By name: k8s/ also holds the InferenceService, which has its own test file.
    for path in (K8S / "deployment.yaml", K8S / "service.yaml"):
        for document in yaml.safe_load_all(path.read_text()):
            if not document:
                continue
            assert document.get("kind") not in forbidden_kinds, (
                f"{path.name} declares a {document['kind']} — that is a later week"
            )
            leaked = set(keys(document)) & forbidden_keys
            assert not leaked, f"{path.name} uses {leaked} — that is a later week"
