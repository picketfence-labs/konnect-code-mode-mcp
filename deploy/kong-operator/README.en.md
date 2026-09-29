# Deploying Kong Operator and Connecting to Konnect

> Japanese (authoritative): [README.md](README.md) — this English version is a translation.

Steps to install Kong Operator on Minikube and connect Konnect Control Plane / DataPlane. This document consolidates the real operating procedure, which was based on the internal SE guide (`Kong Operator Context Mesh - SE's.md`, managed in the Obsidian Vault) and `~/LOCAL_REPO/context-mesh` (reference clone, **do not modify**), into this repository ([ADR-0003](../../docs/decisions/0003-repo-consolidation.md), Japanese).

**Division of responsibilities** ([CLAUDE.md](../../CLAUDE.md), Japanese): The agent may perform Kubernetes/Helm operations (Steps 0–3). The **user (Shinichi) performs Step 4**, creating the MCP Server and checking its status in the Konnect UI; the agent does not operate the Konnect UI directly.

## Prerequisites

- Minikube is running (driver=docker, macOS), and `kubectl` is connected to the cluster.
- A Konnect Personal Access Token (KPAT) is available. **Never store it in files, commits, or logs** (pass it only through the `${KPAT}` environment variable below).

## Step 0. Prepare the Helm repository

```bash
helm repo add kong https://charts.konghq.com   # 未登録の場合のみ
helm repo update
```

## Step 1. Install or upgrade Kong Operator

```bash
helm upgrade --install kong-operator kong/kong-operator \
  --version 1.4.0 \
  -n kong-system --create-namespace \
  --set image.repository=docker.io/kong/nightly-kong-operator \
  --set-string image.tag=20260904 \
  --set env.FEATURE_GATES=mcp-server \
  --set env.ENABLE_CONTROLLER_KONNECT=true
```

⚠️ **Always pass `image.tag` with `--set-string`**. With `--set`, a numeric-looking string such as `20260904` is incorrectly converted to int64. This causes Pods to crash permanently with `InvalidImageName`, while `--wait` times out with the unrelated `client rate limiter Wait returned an error: context deadline exceeded`. Details: [troubleshooting-log.md](../../docs/troubleshooting-log.md) “Helm `--set` numeric type conversion” (Japanese).

`image.tag=20260904` was the latest nightly as of 2026-09-04; [ADR-0005](../../docs/decisions/0005-kong-operator-image-tag-upgrade.md) records that it fixes the Konnect status visibility bug. Use `--set-string` in the same way when following a newer nightly tag.

Verification:

```bash
kubectl -n kong-system rollout status deploy/kong-operator-kong-operator-controller-manager
```

## Step 2. Connect Konnect Control Plane / DataPlane

```bash
export KPAT=kpat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
envsubst < deploy/kong-operator/konnect-resources.yaml.template | kubectl apply -f -
```

The contents of `konnect-resources.yaml.template` ([konnect-resources.yaml.template](konnect-resources.yaml.template)):

- `KonnectAPIAuthConfiguration`: stores KPAT as a Secret-like value (`spec.token` is stored in plain text, but in a dedicated CRD rather than a Kubernetes Secret. Do not take it outside the cluster.)
- `KonnectGatewayControlPlane` (name `test`): creates Control Plane `context-mesh-demo` in Konnect.
- `KonnectExtension` (name `my-konnect-config`): connection settings for the Control Plane above.
- `DataPlane` (name `dataplane`): `kong/kong-gateway:3.15`, replicas 1 (the internal SE guide used `3.14` / replicas 3; this repository was verified with `3.15` / replicas 1, Ready and Healthy in the Konnect UI).

## Step 3. Verify DataPlane is Ready

```bash
kubectl wait --timeout=3m dataplane dataplane --for=condition=Ready
kubectl get dataplane dataplane -o jsonpath='{.status.conditions}'
```

## Step 4. Create an MCP Server (Konnect UI; performed by the user)

The following steps are performed in the Konnect UI (the agent does not execute them; it provides the steps and asks the user to verify):

1. In the Konnect UI, select “Create new MCP Server”.
2. Select Add Existing API → upload the OpenAPI spec (for this demo, [mock-api/openapi.json](../../mock-api/openapi.json)).
3. Select the Control Plane (`context-mesh-demo`) created in Steps 1–3.
4. Verify that the MCP Server Status becomes **Healthy**.

After deployment, the Context Mesh runtime is exposed on Kong DP at route `/mcp/<mcp-server-name>`.

## Verified operating state (2026-09-04)

The following state was verified on 2026-09-04:
- `helm -n kong-system list` → `kong-operator` is `deployed`, chart `kong-operator-1.4.0`, image tag `20260904`.
- `kubectl get dataplane dataplane` → `Ready: True`.
- `kubectl get konnectgatewaycontrolplane test` → `Programmed: True`.
- Existing MCP Server “world-monthly-temperature” showed Status: Healthy in Konnect UI (verified by the user; see [ADR-0005](../../docs/decisions/0005-kong-operator-image-tag-upgrade.md)).

## Cleanup

```bash
kubectl delete -f <(envsubst < deploy/kong-operator/konnect-resources.yaml.template)
helm -n kong-system uninstall kong-operator
```

The user removes the Control Plane / MCP Server from the Konnect UI.
