# Kubernetes manifests

Replace each `<fill in>` in the two files in this directory:

- `deployment.yaml`: a Deployment named `diabetes-api` with two pods. The pods carry the label
  `app: diabetes-api` and run the image `diabetes-api:local` with `imagePullPolicy: IfNotPresent`.
  The container listens on port 8000; name that port `http`. It has a readiness and a liveness
  probe, both on `GET /health`.
- `service.yaml`: a Service named `diabetes-api` that selects the pods by their label and sends
  its port 80 to the container port `http`.

Without `imagePullPolicy`, Kubernetes chooses the policy from the tag: `IfNotPresent` for a tag
such as `:local`, and `Always` for `:latest` or no tag. Setting it makes the manifest work with
any tag.

`make k8s-deploy` applies every `.yaml` file here. `tests/test_k8s_manifests.py` checks the
files without a cluster.

References:
https://kubernetes.io/docs/concepts/workloads/controllers/deployment/ ·
https://kubernetes.io/docs/concepts/services-networking/service/ ·
https://kubernetes.io/docs/concepts/containers/images/#image-pull-policy ·
https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
