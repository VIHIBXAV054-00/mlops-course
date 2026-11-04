"""The Kubernetes manifests in `k8s/`, checked as YAML data. No cluster needed."""

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


def _container(deployment: dict) -> dict:
    return deployment["spec"]["template"]["spec"]["containers"][0]


# ── A Deployment, a Service and probes (Exercise 5) ─────────────────────────


@pytest.mark.skip(reason="Exercise 5 — fill in the Deployment and the Service, then delete this skip marker.")
def test_every_placeholder_is_replaced(deployment, service):
    """A `<fill in>` left in a manifest makes kubectl reject it."""

    def empty(node, where=""):
        if node is None or node == "<fill in>":
            yield where
        elif isinstance(node, dict):
            for key, value in node.items():
                yield from empty(value, f"{where}.{key}" if where else key)
        elif isinstance(node, list):
            for index, item in enumerate(node):
                yield from empty(item, f"{where}[{index}]")

    for name, manifest in (("deployment.yaml", deployment), ("service.yaml", service)):
        blanks = list(empty(manifest))
        assert not blanks, f"k8s/{name}: fill in {', '.join(blanks)}"


@pytest.mark.skip(reason="Exercise 5 — fill in the Deployment and the Service, then delete this skip marker.")
def test_the_manifests_are_the_kinds_they_claim(deployment, service):
    assert deployment["kind"] == "Deployment"
    assert service["kind"] == "Service"


@pytest.mark.skip(reason="Exercise 5 — fill in the Deployment and the Service, then delete this skip marker.")
def test_more_than_one_replica(deployment):
    """When one pod stops, the Service needs another pod to send traffic to."""
    assert deployment["spec"]["replicas"] >= 2


@pytest.mark.skip(reason="Exercise 5 — fill in the Deployment and the Service, then delete this skip marker.")
def test_the_deployment_selector_matches_its_own_template(deployment):
    assert deployment["spec"]["selector"]["matchLabels"].items() <= (
        deployment["spec"]["template"]["metadata"]["labels"].items()
    )


@pytest.mark.skip(reason="Exercise 5 — fill in the Deployment and the Service, then delete this skip marker.")
def test_the_service_selector_matches_the_pod_labels(deployment, service):
    """A mismatch gives no error: the Service has no endpoints, and port-forward hangs."""
    pod_labels = deployment["spec"]["template"]["metadata"]["labels"]
    selector = service["spec"]["selector"]
    assert selector.items() <= pod_labels.items(), (
        f"Service selector {selector} does not match pod labels {pod_labels}: "
        "the Service will have no endpoints"
    )


@pytest.mark.skip(reason="Exercise 5 — fill in the Deployment and the Service, then delete this skip marker.")
def test_a_side_loaded_image_is_not_pulled(deployment):
    """An image copied in with `kind load docker-image` is in no registry."""
    assert _container(deployment).get("imagePullPolicy") == "IfNotPresent", (
        "set imagePullPolicy: IfNotPresent explicitly: the default depends on the tag, "
        "and with :latest or no tag Kubernetes pulls from a registry"
    )


@pytest.mark.skip(reason="Exercise 5 — fill in the Deployment and the Service, then delete this skip marker.")
def test_nothing_from_a_later_week_is_in_the_manifests():
    """This week: a Deployment, a Service and probes. Ingress and autoscaling are out of scope."""
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

    for path in sorted(K8S.glob("*.yaml")):
        for document in yaml.safe_load_all(path.read_text()):
            if not document:
                continue
            assert document.get("kind") not in forbidden_kinds, (
                f"{path.name} declares a {document['kind']}, which a later week introduces"
            )
            leaked = set(keys(document)) & forbidden_keys
            assert not leaked, f"{path.name} uses {leaked}, which a later week introduces"



@pytest.mark.skip(reason="Exercise 5 — fill in the probes, then delete this skip marker.")
def test_both_probes_exist_and_call_a_real_route(deployment):
    """A probe on a path the app does not serve never passes."""
    from week_09_serving.api import create_app

    routes = {getattr(r, "path", None) for r in create_app().routes}
    container = _container(deployment)

    for probe in ("readinessProbe", "livenessProbe"):
        assert probe in container, f"{probe} missing"
        path = container[probe]["httpGet"]["path"]
        assert path in routes, f"{probe} calls {path}, which the app does not serve"


@pytest.mark.skip(reason="Exercise 5 — fill in the probes, then delete this skip marker.")
def test_the_probes_use_the_named_container_port(deployment):
    container = _container(deployment)
    name = container["ports"][0].get("name")
    assert name, "give the container port a name"
    for probe in ("readinessProbe", "livenessProbe"):
        assert container[probe]["httpGet"]["port"] == name


@pytest.mark.skip(reason="Exercise 5 — fill in the probes, then delete this skip marker.")
def test_liveness_is_slower_to_fire_than_readiness(deployment):
    """Liveness restarts the container, so it must wait longer than readiness."""
    container = _container(deployment)
    ready, live = container["readinessProbe"], container["livenessProbe"]

    def budget(probe):
        """Seconds until the probe gives up, with Kubernetes' defaults for missing fields."""
        return (probe.get("initialDelaySeconds", 0)
                + probe.get("periodSeconds", 10) * probe.get("failureThreshold", 3))

    ready_budget, live_budget = budget(ready), budget(live)
    assert live_budget > ready_budget, (
        f"liveness fails after {live_budget}s and readiness after {ready_budget}s: "
        "a slow start would end in a restart loop"
    )
