# Deploying the Insurance API and Registering It in Context Mesh

> Japanese (authoritative): [README.md](README.md) — this English version is a translation.

## What this is

This directory contains fixed copies of the manifests for the 6 Insurance APIs already running in the `insurance` namespace (method B'). It uses the existing Control Plane / Data Plane and does not create new KongService / KongRoute resources. See [ADR-0008](../../docs/decisions/0008-insurance-integration.md) for the decision background (Japanese).

## Apply and verify

These manifests specify the bundle's default image tag `v0.1.1`. Applying them to the current cluster is expected to match the existing objects.

```bash
kubectl diff -f deploy/insurance/services.yaml
kubectl apply -f deploy/insurance/services.yaml
kubectl -n insurance get pods
```

To check any API directly from Mac, start port-forwarding in another terminal.

```bash
kubectl -n insurance port-forward svc/product 8000:8000
```

```bash
curl http://localhost:8000/health
```

## OpenAPI specifications to register in Context Mesh

This demo registers the bundle's OpenAPI specifications (v0.1.3, OpenAPI 3.1.0) **as-is**. Since v0.1.2, each specification's `servers` points to the in-cluster Service DNS (`http://<svc>.insurance.svc.cluster.local:8000`), so no changes are needed. The point of this demo is that registering the local OpenAPI specifications as-is turns them into an MCP Server ([ADR-0008](../../docs/decisions/0008-insurance-integration.md)).

| Source name (from spec `info.title`) | Bundle spec (v0.1.3) | Upstream URL (spec `servers`) | Operations |
|---|---|---|---:|
| `property-insurance-product-api` | [`services/product/openapi.yaml`](https://github.com/picketfence-labs/kong-api-bundle-insurance/blob/v0.1.3/services/product/openapi.yaml) | `http://product.insurance.svc.cluster.local:8000` | 6 |
| `property-insurance-customer-api` | [`services/customer/openapi.yaml`](https://github.com/picketfence-labs/kong-api-bundle-insurance/blob/v0.1.3/services/customer/openapi.yaml) | `http://customer.insurance.svc.cluster.local:8000` | 6 |
| `property-insurance-premium-simulation-api` | [`services/simulation/openapi.yaml`](https://github.com/picketfence-labs/kong-api-bundle-insurance/blob/v0.1.3/services/simulation/openapi.yaml) | `http://simulation.insurance.svc.cluster.local:8000` | 2 |
| `property-insurance-application-api` | [`services/application/openapi.yaml`](https://github.com/picketfence-labs/kong-api-bundle-insurance/blob/v0.1.3/services/application/openapi.yaml) | `http://application.insurance.svc.cluster.local:8000` | 6 |
| `property-insurance-policy-api` | [`services/policy/openapi.yaml`](https://github.com/picketfence-labs/kong-api-bundle-insurance/blob/v0.1.3/services/policy/openapi.yaml) | `http://policy.insurance.svc.cluster.local:8000` | 6 |
| `property-insurance-claim-api` | [`services/claim/openapi.yaml`](https://github.com/picketfence-labs/kong-api-bundle-insurance/blob/v0.1.3/services/claim/openapi.yaml) | `http://claim.insurance.svc.cluster.local:8000` | 6 |

In v0.1.1 and earlier, `servers` still used example domains (`https://api.example.com/<svc>`), so `execute` could not reach the upstream API after registration. If you cloned the bundle locally, check out v0.1.3 or later before pasting. The registered specification's `servers` becomes the default upstream URL used by the MCP Server.

In v0.1.3, all summaries and descriptions are in English. Context Mesh `search` also searches English descriptions, so it can find the intended Tool with terms absent from its name (for example, `underwriting` and `premium`; see “Notes” below).

The Pods still use image `v0.1.1`. Changes under `services/` from v0.1.1 through v0.1.3 are limited to OpenAPI specifications and API descriptions (summary, description, and parameter descriptions); parameters and constraints did not change.

## Register in the Konnect UI

Follow the same order as [INSTRUCTIONS.md §2](../../INSTRUCTIONS.en.md): create an MCP Server → register API Sources → select a Data Plane.

1. In the Konnect UI **Context Mesh**, create an **MCP Server** named `kong-insurance`.
2. Register the 6 API Sources in the table above, one by one, by pasting the bundle specifications (v0.1.3) as-is.
3. Select the existing Data Plane used by the World Weather MCP Server. Do not create a new Control Plane.
4. After saving, check the status and tool list on the MCP Server overview page.

The MCP URL is `http://127.0.0.1/mcp/kong-insurance` (through `minikube tunnel`).

### Items to check and record after registration

- `tools/list` shows these 4 Tools: `list_tools` / `search` / `get_schema` / `execute`.
- `list_tools` shows **32** API Tools (6 / 6 / 2 / 6 / 6 / 6 per Source). Tool names follow `<Source name>_<operationId>`; `-` in a Source name becomes `_dash_` (example: `property_dash_insurance_dash_product_dash_api_list_products_products_get`).
- MCP Server health status.
- List Tools return `{total, items}` and paginate with `skip` / `limit` (`limit` maximum is 100).

## Notes

- **Write operations are exposed too.** Registering the bundle specifications as-is also creates Tools for API creation, updates, and deletion (POST / PUT / DELETE). In the demo, Chat UI instructions limit use to reading and premium simulation. Each Pod keeps data in memory; restarting it restores the seed state if data was changed.

  ```bash
  kubectl -n insurance rollout restart deploy
  ```

- Customer data is fictional but includes values resembling Japanese My Number identifiers. Do not output individual customer rows in demo responses.
- Some Python standard library modules cannot be imported in Code Mode `execute` (observed on 2026-09-29: `collections` and `statistics` raised `ModuleNotFoundError`; `asyncio`, `json`, `math`, `re`, and `datetime` worked. The result was the same for World Weather and `kong-insurance`). Write aggregations using built-in features only.
- `search` does not return results for Japanese queries (observed as of 2026-09-29). It searches Tool names and English descriptions using exact, word-level matches. Search in English (for example, `list applications`, `premium quote`, `paid claims`). Since every Source name begins with `property-insurance-`, `insurance` and `property` match every Tool and do not help narrow results.
