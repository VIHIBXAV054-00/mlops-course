"""The Kubernetes manifests, checked as data.

Same idea as Week 7's `test_workflows.py`: a cluster is not available in the
autograder, but a manifest is a YAML file, and most of what goes wrong with a
first Deployment is structural. These assertions run in milliseconds and catch
the two failures that otherwise cost an afternoon each — both of which fail
SILENTLY rather than loudly.
"""

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
    """**The silent one.** Break this and nothing errors.

    A Service selects pods by LABEL, not by Deployment name. If the selector
    and the pod template labels disagree, the Service is created successfully,
    `kubectl get svc` looks entirely normal, and `kubectl port-forward`
    connects and then hangs forever — because the Service has no endpoints
    behind it.

    Two lines of test for an hour of confusion. `kubectl get endpoints` is the
    command that would have told you.
    """
    pod_labels = deployment["spec"]["template"]["metadata"]["labels"]
    selector = service["spec"]["selector"]
    assert selector.items() <= pod_labels.items(), (
        f"Service selector {selector} does not match pod labels {pod_labels} — "
        "the Service will have zero endpoints and port-forward will hang"
    )


def test_the_deployment_selector_matches_its_own_template(deployment):
    """Kubernetes rejects this one at apply time, which is the kinder failure."""
    assert deployment["spec"]["selector"]["matchLabels"].items() <= (
        deployment["spec"]["template"]["metadata"]["labels"].items()
    )


def test_a_side_loaded_image_is_not_pulled(deployment):
    """**The other silent one**, and the most common first-day Kubernetes error.

    `kind load docker-image` copies an image into the cluster nodes' own image
    store. It exists in no registry. Unless `imagePullPolicy` says otherwise,
    Kubernetes still tries to pull it and sits in `ErrImagePull` forever.

    Both halves are required: the load AND the policy. Either one alone fails.
    """
    container = deployment["spec"]["template"]["spec"]["containers"][0]
    assert container.get("imagePullPolicy") == "IfNotPresent", (
        "a locally-built image side-loaded with `kind load docker-image` will "
        "sit in ErrImagePull unless imagePullPolicy is IfNotPresent"
    )


def test_both_probes_exist_and_point_at_a_real_route(deployment):
    """The probe paths must be routes the app actually serves.

    A probe pointing at `/healthz` when the app serves `/health` produces pods
    that never become ready, with an error that says nothing about the typo.
    """
    from week_10_kserve_rollout.api import create_app

    routes = {getattr(r, "path", None) for r in create_app().routes}
    container = deployment["spec"]["template"]["spec"]["containers"][0]

    for probe in ("readinessProbe", "livenessProbe"):
        assert probe in container, f"{probe} missing"
        path = container[probe]["httpGet"]["path"]
        assert path in routes, f"{probe} probes {path}, which the app does not serve"


def test_liveness_is_slower_to_fire_than_readiness(deployment):
    """Readiness withholds traffic; liveness KILLS the container.

    The second is much more violent, so it should be slower to trigger. A
    liveness probe that fires before a slow start finishes turns a cold start
    into a restart loop — the pod is killed, restarts, is killed again, and the
    logs show nothing except repeated startup.
    """
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
    """Week 9's fence, enforced — and NARROWED IN WEEK 10.

    Ingress and autoscaling are still later material. Traffic splitting and the
    InferenceService are not: Week 10 introduces both, so this guard now checks
    only the two files it was written about, and the KServe manifests have their
    own guard in `test_isvc_manifests.py`.

    That narrowing is the same lifecycle `test_scope.py` follows — a guard is
    tied to the week whose scope it describes, and the week that legitimately
    introduces a thing is the week that stops forbidding it. Widen this glob back
    to `k8s/*.yaml` and it starts failing on a manifest that is supposed to
    exist, which is how a guard earns a `# noqa` and stops being read.

    Scanned against the PARSED documents, not the file text — a comment
    explaining that Ingress is out of scope must not trip a guard looking for
    an Ingress. Same lesson as Week 7's scope audit: keep the guard's clean
    state at zero hits, or people stop reading it.
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

    # Week 9's own manifests, by name. Not a glob: k8s/ now also holds this
    # week's InferenceService, a kind cluster config and a Job template.
    for path in (K8S / "deployment.yaml", K8S / "service.yaml"):
        for document in yaml.safe_load_all(path.read_text()):
            if not document:
                continue
            assert document.get("kind") not in forbidden_kinds, (
                f"{path.name} declares a {document['kind']} — that is a later week"
            )
            leaked = set(keys(document)) & forbidden_keys
            assert not leaked, f"{path.name} uses {leaked} — that is a later week"
