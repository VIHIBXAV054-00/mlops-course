# The manifests

| File | What it is |
| --- | --- |
| `inferenceservice.yaml` | the running version: our image, serving model v1 from the store |
| `inferenceservice-canary.yaml` | **you write it in Exercise 3** |
| `model-store.yaml` | the PersistentVolume and Claim over the `model-store/` folder |
| `kind-cluster.yaml` | the cluster: mounts `model-store/` into the node, maps host port 5550 to the gateway |
| `job.yaml` | the template `make split-measure`, `make smoke` and `make loadtest` run inside the cluster |
| `deployment.yaml`, `service.yaml` | Week 9's Deployment and Service, for comparison |

## `inferenceservice-canary.yaml` (Exercise 3)

Copy `inferenceservice.yaml` and change two things:

- add `canaryTrafficPercent` under `spec.predictor`, with the `canary.percent` of your `release.yaml`;
- point `STORAGE_URI` at the candidate version of your `release.yaml`.

Change nothing else: `tests/test_isvc_manifests.py` checks that the two files differ in exactly
these two places. Reference: https://kserve.github.io/website/docs/model-serving/predictive-inference/rollout-strategies/canary-example
