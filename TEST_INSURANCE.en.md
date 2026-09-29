# TEST_INSURANCE — Insurance Test Cases

> Japanese (authoritative): [TEST_INSURANCE.md](TEST_INSURANCE.md) — this English version is a translation.

The Insurance use case registers local OpenAPI specifications in Context Mesh as-is to create an MCP Server, selects the required Tools from 6 APIs and 32 Tools, then joins and aggregates applications, policies, claims, and products. For the temperature-data use case that demonstrates token reduction through sandbox aggregation, see [TEST_WORLD_WEATHER.md](TEST_WORLD_WEATHER.en.md).

## Test environment

Based on measured evidence captured on 2026-09-29 in `docs/evidence/insurance-2026-09-29/`.

| Item | Value |
|---|---|
| Date and time | 2026-09-29 15:47–15:52 JST (06:47–06:52 UTC) |
| Chat UI | `main` `a57553b` (including simultaneous connection to 2 MCP Servers from PR #24), built with `next build` and run locally with `next start -p 3100`. `MCP_WEATHER_URL=http://127.0.0.1/mcp/world-monthly-temperature`, `MCP_INSURANCE_URL=http://127.0.0.1/mcp/kong-insurance` (through `minikube tunnel`). Not the Chat UI running in the cluster (`chat-ui:0.1.0`). |
| LLM | `gemini-3.5-flash` (Chat UI default) |
| MCP Server | `kong-insurance` (Context Mesh MCP Server 3.3.1, runner `kong/mcp-server-runner:0.6.0`). 6 Sources, 32 Tools. |
| Registered spec | `services/<svc>/openapi.yaml` from kong-api-bundle-insurance **v0.1.3**, registered as-is (English summaries / descriptions). |
| Tool names | `property_dash_insurance_dash_<svc>_dash_api_<operationId>` (for simulation: `property_dash_insurance_dash_premium_dash_simulation_dash_api_...`) |
| Insurance API | `insurance` namespace, image `v0.1.1` (seed state; no write operations were run). |
| Japanese questions | Run from a browser (Playwright); screenshots saved. |
| English questions | Sent directly to the Chat UI API (`POST /chat-ui/api/chat`). No screenshots. Full answers are in `docs/evidence/insurance-2026-09-29/I-*-en-answer.md`. |

## Target APIs and data model

The Insurance bundle ([kong-api-bundle-insurance](https://github.com/picketfence-labs/kong-api-bundle-insurance)) provides six services for property and casualty insurance operations as REST APIs. Each service is a separate API (Source), and the MCP Server `kong-insurance` exposes all six together. The data is a fixed seed and returns to its initial state when the Pods restart.

[![kong-api-bundle-insurance data model (ER diagram)](assets/images/insurance-data-model.png)](https://picketfence-labs.github.io/diagrams/c5bfcf04d3a2/)

Click the image to open the interactive version (supports pan, zoom, and search). The ER diagram and field definitions come from [`docs/DATA.md` in the bundle](https://github.com/picketfence-labs/kong-api-bundle-insurance/blob/v0.1.3/docs/DATA.md) (v0.1.3).

| Service | Role | Records | Main keys and relationships |
|---|---|---:|---|
| product | Product master (fire, auto, accident, medical, pet) | 5 | `product_id` (`PRD-001` to `PRD-005`) |
| customer | Customer master | 100 | `customer_id`. Referenced by applications, policies, and claims |
| application | Application | 300 | `product_id`, `customer_id`. 200 of them became policies and have `resulting_policy_id` |
| policy | Policy | 200 | `application_id` (1:1 with the accepted application), `product_id`, `customer_id` |
| claim | Insurance claim | 50 | `policy_id` (the claimed policy), `customer_id`. Has `status` and `claim_amount_paid` |
| simulation | Premium simulation | – | Only calculates from `product_id`, age, coverage amount, and so on; stores nothing |

The test cases follow these relationships:

- I-1: For each product, count applications and policies by `product_id` and compare them
- I-2: Follow claim → policy (`policy_id`) → product (`product_id`) to assign each claim to a product. Claims do not have `product_id`, so this join is required
- I-3: Pass `product_id`, date of birth, and coverage amount to simulation. No data is changed

customer contains names, addresses, My Number-format values, and similar fields (fictitious data). These tests do not output customer personal information in answers or logs.

## How to run

Configure both World Weather (`/mcp/world-monthly-temperature`) and Insurance (`/mcp/kong-insurance`) URLs in Chat UI, then submit each case's question. Tool names `weather_` / `insurance_` distinguish the destination. See [Chat UI settings in deploy/README.md](deploy/README.en.md#chat-ui-nextjs--vercel-ai-sdk--mcp-client) and [deploy/insurance/README.md](deploy/insurance/README.en.md) for setup.

## I-1: Conversion rate from applications to policies

### Test description

Fetch products, applications, and policies from separate APIs, aggregate by product ID, and return the 5 products with the highest conversion rate (policy count ÷ application count).

### Input

- Japanese: 「商品ごとに申込件数と成立した契約件数を集計し、成立率の高い順に上位5商品を示してください。申込と契約は別のAPIから取得してください。」
- English: "For each insurance product, count applications and issued policies, then show the top five by policy conversion rate. Retrieve applications and policies from their respective APIs."

### Expected processing

`insurance_list_tools` → `insurance_get_schema` → `insurance_execute` ×2 (both Japanese and English). The first `execute` checks the data shape; the final `execute` fetches products, 300 applications (3 pages of 100), and 200 policies (2 pages of 100), then aggregates them.

### Baseline

Baseline computed directly from seed data. Display conversion rate (policy count ÷ application count) as a percentage with 2 decimal places.

| Rank | Product | Applications | Policies | Conversion rate |
|---:|---|---:|---:|---:|
| 1 | 自動車保険「ドライブセーフ」 | 54 | 40 | 74.07% |
| 2 | 傷害保険「ケガの安心サポート」 | 59 | 41 | 69.49% |
| 3 | ペット保険「わんにゃんメディカル」 | 68 | 46 | 67.65% |
| 4 | 火災保険「住まいの安心」 | 71 | 45 | 63.38% |
| 5 | 医療保険「メディカルサポート」 | 48 | 28 | 58.33% |

### Output

The Japanese browser response and English direct API response matched the 5 rows above in order and values. The full English response is `docs/evidence/insurance-2026-09-29/I-1-en-answer.md`. There is no screenshot of the English run.

### Screenshot

![I-1 Japanese Chat UI result](assets/images/chat-ui-insurance-i1-conversion-rate.png)

### Logs

Tool call order (`toolCalls`): `insurance_list_tools` → `insurance_get_schema` → `insurance_execute` → `insurance_execute`.

**Generated code and result from the final `execute`** (excerpt from `docs/evidence/insurance-2026-09-29/I-1-ja-mcp-server.log`):

```text
# execute 2/2（ログへの出力時刻は次のリクエスト到着時。Code Modeのrunnerは1リクエスト遅れて書き出す）
2026-09-29T06:48:10.941179756Z ============================================================
2026-09-29T06:48:10.941185881Z CODE MODE — Generated Python:
2026-09-29T06:48:10.941210214Z ============================================================
2026-09-29T06:48:10.941212631Z async def aggregate():
2026-09-29T06:48:10.941213797Z     prod_res = await call_tool("property_dash_insurance_dash_product_dash_api_list_products_products_get", {"limit": 100})
2026-09-29T06:48:10.941215172Z     products = prod_res.get("items", [])
2026-09-29T06:48:10.941216256Z     prod_map = {p["product_id"]: p["product_name"] for p in products}
2026-09-29T06:48:10.941217464Z     
2026-09-29T06:48:10.941218422Z     apps = []
2026-09-29T06:48:10.941219297Z     skip = 0
2026-09-29T06:48:10.941220047Z     limit = 100
2026-09-29T06:48:10.941220797Z     while True:
2026-09-29T06:48:10.941221589Z         res = await call_tool("property_dash_insurance_dash_application_dash_api_list_applications_applications_get", {"skip": skip, "limit": limit})
2026-09-29T06:48:10.941222631Z         items = res.get("items", [])
2026-09-29T06:48:10.941223464Z         if not items:
2026-09-29T06:48:10.941224214Z             break
2026-09-29T06:48:10.941225006Z         apps.extend(items)
2026-09-29T06:48:10.941228381Z         if len(apps) >= res.get("total", 0):
2026-09-29T06:48:10.941229964Z             break
2026-09-29T06:48:10.941230714Z         skip += limit
2026-09-29T06:48:10.941231506Z         
2026-09-29T06:48:10.941236964Z     pols = []
2026-09-29T06:48:10.941239339Z     skip = 0
2026-09-29T06:48:10.941241464Z     limit = 100
2026-09-29T06:48:10.941246131Z     while True:
2026-09-29T06:48:10.941250172Z         res = await call_tool("property_dash_insurance_dash_policy_dash_api_list_policies_policies_get", {"skip": skip, "limit": limit})
2026-09-29T06:48:10.941271797Z         items = res.get("items", [])
2026-09-29T06:48:10.941288006Z         if not items:
2026-09-29T06:48:10.941289797Z             break
2026-09-29T06:48:10.941290464Z         pols.extend(items)
2026-09-29T06:48:10.941291089Z         if len(pols) >= res.get("total", 0):
2026-09-29T06:48:10.941291797Z             break
2026-09-29T06:48:10.941292422Z         skip += limit
2026-09-29T06:48:10.941293047Z 
2026-09-29T06:48:10.941293672Z     app_counts = {}
2026-09-29T06:48:10.941294256Z     pol_counts = {}
2026-09-29T06:48:10.941294881Z     
2026-09-29T06:48:10.941295506Z     for pid in prod_map:
2026-09-29T06:48:10.941296131Z         app_counts[pid] = 0
2026-09-29T06:48:10.941300506Z         pol_counts[pid] = 0
2026-09-29T06:48:10.941302006Z         
2026-09-29T06:48:10.941303631Z     for app in apps:
2026-09-29T06:48:10.941307672Z         pid = app.get("product_id")
2026-09-29T06:48:10.941312422Z         if pid in app_counts:
2026-09-29T06:48:10.941316256Z             app_counts[pid] += 1
2026-09-29T06:48:10.941320589Z             
2026-09-29T06:48:10.941324172Z     for pol in pols:
2026-09-29T06:48:10.941325006Z         pid = pol.get("product_id")
2026-09-29T06:48:10.941325672Z         if pid in pol_counts:
2026-09-29T06:48:10.941329714Z             pol_counts[pid] += 1
2026-09-29T06:48:10.941333381Z             
2026-09-29T06:48:10.941336547Z     results = []
2026-09-29T06:48:10.941339797Z     for pid, pname in prod_map.items():
2026-09-29T06:48:10.941340672Z         acount = app_counts[pid]
2026-09-29T06:48:10.941342422Z         pcount = pol_counts[pid]
2026-09-29T06:48:10.941345797Z         ratio = pcount / acount if acount > 0 else 0.0
2026-09-29T06:48:10.941350131Z         results.append({
2026-09-29T06:48:10.941353964Z             "product_id": pid,
2026-09-29T06:48:10.941369964Z             "product_name": pname,
2026-09-29T06:48:10.941373881Z             "application_count": acount,
2026-09-29T06:48:10.941377297Z             "policy_count": pcount,
2026-09-29T06:48:10.941382589Z             "success_rate": round(ratio * 100, 2)  # パーセント表記（小数点以下2桁）
2026-09-29T06:48:10.941386714Z         })
2026-09-29T06:48:10.941388381Z         
2026-09-29T06:48:10.941390631Z     results_sorted = sorted(results, key=lambda x: x["success_rate"], reverse=True)
2026-09-29T06:48:10.941395881Z     return results_sorted[:5]
2026-09-29T06:48:10.941403381Z 
2026-09-29T06:48:10.941416797Z return await aggregate()
2026-09-29T06:48:10.941420881Z ============================================================
2026-09-29T06:48:10.941424839Z Available tools: ['call_tool']
2026-09-29T06:48:10.941429006Z Result: [{'product_id': 'PRD-002', 'product_name': '自動車保険「ドライブセーフ」', 'application_count': 54, 'policy_count': 40, 'success_rate': 74.07}, {'product_id': 'PRD-003', 'product_name': '傷害保険「ケガの安心サポート」', 'application_count': 59, 'policy_count': 41, 'success_rate': 69.49}, {'product_id': 'PRD-005', 'product_name': 'ペット保険「わんにゃんメディカル」', 'application_count': 68, 'policy_count': 46, 'success_rate': 67.65}, {'product_id': 'PRD-001', 'product_name': '火災保険「住まいの安心」', 'application_count': 71, 'policy_count': 45, 'success_rate': 63.38}, {'product_id': 'PRD-004', 'product_name': '医療保険「メディカルサポート」', 'application_count': 48, 'policy_count': 28, 'success_rate': 58.33}]
```

**Upstream Insurance API access logs** (Japanese run; excerpt from `docs/evidence/insurance-2026-09-29/I-1-ja-insurance-api.log`):

```text
2026-09-29T06:47:28.815982458Z [product] INFO:     10.244.1.70:58230 - "GET /products?limit=1 HTTP/1.1" 200 OK
2026-09-29T06:47:28.826299583Z [application] INFO:     10.244.1.70:60978 - "GET /applications?limit=1 HTTP/1.1" 200 OK
2026-09-29T06:47:28.834000500Z [policy] INFO:     10.244.1.70:55900 - "GET /policies?limit=1 HTTP/1.1" 200 OK
2026-09-29T06:47:36.671789712Z [product] INFO:     10.244.1.70:46160 - "GET /products?limit=100 HTTP/1.1" 200 OK
2026-09-29T06:47:36.680620545Z [application] INFO:     10.244.1.70:37252 - "GET /applications?skip=0&limit=100 HTTP/1.1" 200 OK
2026-09-29T06:47:36.691609045Z [application] INFO:     10.244.1.70:37268 - "GET /applications?skip=100&limit=100 HTTP/1.1" 200 OK
2026-09-29T06:47:36.699738670Z [application] INFO:     10.244.1.70:37278 - "GET /applications?skip=200&limit=100 HTTP/1.1" 200 OK
2026-09-29T06:47:36.708038379Z [policy] INFO:     10.244.1.70:35672 - "GET /policies?skip=0&limit=100 HTTP/1.1" 200 OK
2026-09-29T06:47:36.716145712Z [policy] INFO:     10.244.1.70:35684 - "GET /policies?skip=100&limit=100 HTTP/1.1" 200 OK
```

## I-2: Aggregate paid claim amounts by product

### Test description

Resolve a product through the policy linked from each claim, and aggregate by product only claims whose status is “支払済” (paid).

### Input

- Japanese: 「ステータスが「支払済」の保険金請求だけを対象に、支払額を商品別に合計し、上位5商品を示してください。請求対象の契約から商品を特定してください。」
- English: "Consider only insurance claims whose status is 支払済 (paid). Sum the paid amounts by insurance product and show the top five. Resolve each claim's product through its policy."

### Expected processing

Japanese: `insurance_list_tools` → `insurance_get_schema` → `insurance_execute` ×3. English: `insurance_list_tools` → `insurance_get_schema` → `insurance_execute` ×2. Filter on `status == '支払済'`; treat null `claim_amount_paid` as 0. Resolve the product ID through the claim's `policy_id`, then map it to a product name.

### Baseline

Baseline computed directly from seed data. The target set contains 28 “支払済” claims.

| Rank | Product | Total paid amount |
|---:|---|---:|
| 1 | 火災保険「住まいの安心」 | 23,497,720円 |
| 2 | 傷害保険「ケガの安心サポート」 | 9,884,887円 |
| 3 | 自動車保険「ドライブセーフ」 | 4,662,288円 |
| 4 | 医療保険「メディカルサポート」 | 1,250,942円 |
| 5 | ペット保険「わんにゃんメディカル」 | 639,214円 |

### Output

The Japanese browser response and English direct API response matched the 5 rows above in order and values. The answer to the English question was also in Japanese. Full English response: `docs/evidence/insurance-2026-09-29/I-2-en-answer.md`. There is no screenshot of the English run.

#### Run before clarifying the condition

The first Japanese query followed the original design: 「支払済みの保険金請求額を商品別に合計し、上位5商品を示してください。請求対象の契約から商品を特定してください。」 The result **did not match the baseline**: fire ¥39,563,922, accident ¥11,654,702, auto ¥5,872,134, medical ¥1,250,942, and pet ¥886,584 (36 claims). Generated code filtered on `claim_amount_paid > 0`, so it also included claims with status “承認” (approved).

The `toolCalls` for this run were `insurance_list_tools` → `insurance_get_schema` → `insurance_execute` ×2.

State business conditions explicitly in the question. Based on this finding, the current test case explicitly specifies “status is 支払済”.

![I-2 Chat UI result from the run with an ambiguous condition](assets/images/chat-ui-insurance-i2-ambiguous-run.png)

### Screenshot

![I-2 Japanese Chat UI result with the condition explicit](assets/images/chat-ui-insurance-i2-paid-claims.png)

### Logs

Tool call order (`toolCalls`): Japanese `insurance_list_tools` → `insurance_get_schema` → `insurance_execute` ×3. English `insurance_list_tools` → `insurance_get_schema` → `insurance_execute` ×2.

**Generated code and result from the final `execute`** (excerpt from `docs/evidence/insurance-2026-09-29/I-2-ja-mcp-server.log`):

```text
# execute 3/3（ログへの出力時刻は次のリクエスト到着時。Code Modeのrunnerは1リクエスト遅れて書き出す）
2026-09-29T06:50:37.864691046Z ============================================================
2026-09-29T06:50:37.864697796Z CODE MODE — Generated Python:
2026-09-29T06:50:37.864720171Z ============================================================
2026-09-29T06:50:37.864722171Z async def aggregate_claims():
2026-09-29T06:50:37.864723254Z     # 1. 全claimを取得
2026-09-29T06:50:37.864724504Z     claims_res = await call_tool('property_dash_insurance_dash_claim_dash_api_list_claims_claims_get', {'limit': 100})
2026-09-29T06:50:37.864725754Z     claims = claims_res.get('items', [])
2026-09-29T06:50:37.864726838Z     
2026-09-29T06:50:37.864727838Z     # 2. 全policyを取得 (paging)
2026-09-29T06:50:37.864732921Z     policies = []
2026-09-29T06:50:37.864734171Z     skip = 0
2026-09-29T06:50:37.864735171Z     limit = 100
2026-09-29T06:50:37.864738713Z     while True:
2026-09-29T06:50:37.864741963Z         policies_res = await call_tool('property_dash_insurance_dash_policy_dash_api_list_policies_policies_get', {'skip': skip, 'limit': limit})
2026-09-29T06:50:37.864743296Z         items = policies_res.get('items', [])
2026-09-29T06:50:37.864744338Z         if not items:
2026-09-29T06:50:37.864745338Z             break
2026-09-29T06:50:37.864746379Z         policies.extend(items)
2026-09-29T06:50:37.864753671Z         if len(policies) >= policies_res.get('total', 0):
2026-09-29T06:50:37.864760713Z             break
2026-09-29T06:50:37.864766629Z         skip += limit
2026-09-29T06:50:37.864772129Z 
2026-09-29T06:50:37.864778504Z     # 3. 全productを取得
2026-09-29T06:50:37.864785213Z     products_res = await call_tool('property_dash_insurance_dash_product_dash_api_list_products_products_get', {'limit': 100})
2026-09-29T06:50:37.864788171Z     products = products_res.get('items', [])
2026-09-29T06:50:37.864791546Z 
2026-09-29T06:50:37.864792504Z     # マッピング辞書作成
2026-09-29T06:50:37.864793671Z     # product_id -> product_name
2026-09-29T06:50:37.864794796Z     product_map = {}
2026-09-29T06:50:37.864795754Z     for p in products:
2026-09-29T06:50:37.864796713Z         product_map[p['product_id']] = p['product_name']
2026-09-29T06:50:37.864797838Z         
2026-09-29T06:50:37.864798796Z     # policy_id -> product_id
2026-09-29T06:50:37.864799879Z     policy_map = {}
2026-09-29T06:50:37.864800838Z     for pol in policies:
2026-09-29T06:50:37.864801838Z         policy_map[pol['policy_id']] = pol['product_id']
2026-09-29T06:50:37.864802879Z 
2026-09-29T06:50:37.864803796Z     # 集計
2026-09-29T06:50:37.864804754Z     product_paid_totals = {}
2026-09-29T06:50:37.864808796Z     
2026-09-29T06:50:37.864809838Z     for claim in claims:
2026-09-29T06:50:37.864861421Z         if claim.get('status') == '支払済':
2026-09-29T06:50:37.864866546Z             paid_amount = claim.get('claim_amount_paid', 0)
2026-09-29T06:50:37.864868254Z             if paid_amount is None:
2026-09-29T06:50:37.864869421Z                 paid_amount = 0
2026-09-29T06:50:37.864870546Z             
2026-09-29T06:50:37.864874463Z             policy_id = claim.get('policy_id')
2026-09-29T06:50:37.864875588Z             product_id = policy_map.get(policy_id)
2026-09-29T06:50:37.864876671Z             if product_id:
2026-09-29T06:50:37.864878713Z                 product_name = product_map.get(product_id, f"未知の商品({product_id})")
2026-09-29T06:50:37.864885588Z             else:
2026-09-29T06:50:37.864891379Z                 product_name = "契約情報なし"
2026-09-29T06:50:37.864893504Z                 
2026-09-29T06:50:37.864894671Z             product_paid_totals[product_name] = product_paid_totals.get(product_name, 0) + paid_amount
2026-09-29T06:50:37.864895921Z 
2026-09-29T06:50:37.864901338Z     # ソートして上位5件
2026-09-29T06:50:37.864904588Z     sorted_totals = sorted(product_paid_totals.items(), key=lambda x: x[1], reverse=True)
2026-09-29T06:50:37.864908171Z     
2026-09-29T06:50:37.864909254Z     return sorted_totals[:5]
2026-09-29T06:50:37.864910254Z 
2026-09-29T06:50:37.864911254Z return await aggregate_claims()
2026-09-29T06:50:37.864912338Z ============================================================
2026-09-29T06:50:37.864913463Z Available tools: ['call_tool']
2026-09-29T06:50:37.864914546Z Result: [('火災保険「住まいの安心」', 23497720), ('傷害保険「ケガの安心サポート」', 9884887), ('自動車保険「ドライブセーフ」', 4662288), ('医療保険「メディカルサポート」', 1250942), ('ペット保険「わんにゃんメディカル」', 639214)]
```

**Upstream Insurance API access logs** (Japanese run; excerpt from `docs/evidence/insurance-2026-09-29/I-2-ja-insurance-api.log`):

```text
2026-09-29T06:50:10.950163506Z [claim] INFO:     10.244.1.70:48536 - "GET /claims?limit=1 HTTP/1.1" 200 OK
2026-09-29T06:50:10.962308881Z [policy] INFO:     10.244.1.70:42730 - "GET /policies?limit=1 HTTP/1.1" 200 OK
2026-09-29T06:50:10.980209672Z [product] INFO:     10.244.1.70:57206 - "GET /products?limit=1 HTTP/1.1" 200 OK
2026-09-29T06:50:15.995888258Z [claim] INFO:     10.244.1.70:58638 - "GET /claims?limit=100 HTTP/1.1" 200 OK
2026-09-29T06:50:21.502553552Z [claim] INFO:     10.244.1.70:58642 - "GET /claims?limit=100 HTTP/1.1" 200 OK
2026-09-29T06:50:21.517117552Z [policy] INFO:     10.244.1.70:43736 - "GET /policies?skip=0&limit=100 HTTP/1.1" 200 OK
2026-09-29T06:50:21.542605136Z [policy] INFO:     10.244.1.70:43752 - "GET /policies?skip=100&limit=100 HTTP/1.1" 200 OK
2026-09-29T06:50:21.560092011Z [product] INFO:     10.244.1.70:58694 - "GET /products?limit=100 HTTP/1.1" 200 OK
```

#### Logs from the run with an ambiguous condition

**Generated code and result from the final `execute`** (excerpt from `docs/evidence/insurance-2026-09-29/I-2-ja-ambiguous-mcp-server.log`):

```text
# execute 2/2（ログへの出力時刻は次のリクエスト到着時。Code Modeのrunnerは1リクエスト遅れて書き出す）
2026-09-29T06:49:35.600772878Z ============================================================
2026-09-29T06:49:35.600782587Z CODE MODE — Generated Python:
2026-09-29T06:49:35.600785337Z ============================================================
2026-09-29T06:49:35.600786462Z async def fetch_all(tool_name):
2026-09-29T06:49:35.600787295Z     items = []
2026-09-29T06:49:35.600788087Z     skip = 0
2026-09-29T06:49:35.600788837Z     limit = 100
2026-09-29T06:49:35.600789587Z     while True:
2026-09-29T06:49:35.600790337Z         res = await call_tool(tool_name, {'skip': skip, 'limit': limit})
2026-09-29T06:49:35.600791212Z         items.extend(res.get('items', []))
2026-09-29T06:49:35.600801503Z         total = res.get('total', 0)
2026-09-29T06:49:35.600802628Z         if len(items) >= total or not res.get('items'):
2026-09-29T06:49:35.600831712Z             break
2026-09-29T06:49:35.600833503Z         skip += limit
2026-09-29T06:49:35.600834128Z     return items
2026-09-29T06:49:35.600834753Z 
2026-09-29T06:49:35.600835337Z async def main():
2026-09-29T06:49:35.600835962Z     claims = await fetch_all('property_dash_insurance_dash_claim_dash_api_list_claims_claims_get')
2026-09-29T06:49:35.600836712Z     policies = await fetch_all('property_dash_insurance_dash_policy_dash_api_list_policies_policies_get')
2026-09-29T06:49:35.600837503Z     products = await fetch_all('property_dash_insurance_dash_product_dash_api_list_products_products_get')
2026-09-29T06:49:35.600838212Z     
2026-09-29T06:49:35.600838837Z     prod_map = {p['product_id']: p['product_name'] for p in products}
2026-09-29T06:49:35.600839503Z     policy_map = {pol['policy_id']: pol['product_id'] for pol in policies}
2026-09-29T06:49:35.600840170Z     
2026-09-29T06:49:35.600840795Z     product_totals = {}
2026-09-29T06:49:35.600841420Z     for claim in claims:
2026-09-29T06:49:35.600842003Z         paid_amt = claim.get('claim_amount_paid')
2026-09-29T06:49:35.600842670Z         if paid_amt is not None and paid_amt > 0:
2026-09-29T06:49:35.600843545Z             policy_id = claim.get('policy_id')
2026-09-29T06:49:35.600846878Z             prod_id = policy_map.get(policy_id)
2026-09-29T06:49:35.600847795Z             if prod_id:
2026-09-29T06:49:35.600848545Z                 prod_name = prod_map.get(prod_id, prod_id)
2026-09-29T06:49:35.600849337Z                 product_totals[prod_name] = product_totals.get(prod_name, 0) + paid_amt
2026-09-29T06:49:35.600850253Z             else:
2026-09-29T06:49:35.600850962Z                 product_totals['Unknown Policy'] = product_totals.get('Unknown Policy', 0) + paid_amt
2026-09-29T06:49:35.600851878Z                 
2026-09-29T06:49:35.600852587Z     sorted_totals = sorted(product_totals.items(), key=lambda x: x[1], reverse=True)
2026-09-29T06:49:35.600853587Z     top_5 = sorted_totals[:5]
2026-09-29T06:49:35.600854378Z     
2026-09-29T06:49:35.600855087Z     return {
2026-09-29T06:49:35.600855795Z         'top_5': [{'product_name': name, 'total_paid_amount': amt} for name, amt in top_5],
2026-09-29T06:49:35.600856753Z         'total_claims_processed': len(claims),
2026-09-29T06:49:35.600857628Z         'paid_claims_count': sum(1 for c in claims if c.get('claim_amount_paid') is not None and c.get('claim_amount_paid') > 0)
2026-09-29T06:49:35.600858712Z     }
2026-09-29T06:49:35.600859462Z 
2026-09-29T06:49:35.600860170Z return await main()
2026-09-29T06:49:35.600861920Z ============================================================
2026-09-29T06:49:35.600866128Z Available tools: ['call_tool']
2026-09-29T06:49:35.600872087Z Result: {'top_5': [{'product_name': '火災保険「住まいの安心」', 'total_paid_amount': 39563922}, {'product_name': '傷害保険「ケガの安心サポート」', 'total_paid_amount': 11654702}, {'product_name': '自動車保険「ドライブセーフ」', 'total_paid_amount': 5872134}, {'product_name': '医療保険「メディカルサポート」', 'total_paid_amount': 1250942}, {'product_name': 'ペット保険「わんにゃんメディカル」', 'total_paid_amount': 886584}], 'total_claims_processed': 50, 'paid_claims_count': 36}
```

**Upstream Insurance API access logs** (Japanese run; excerpt from `docs/evidence/insurance-2026-09-29/I-2-ja-ambiguous-insurance-api.log`):

```text
2026-09-29T06:48:20.750465344Z [claim] INFO:     10.244.1.70:59230 - "GET /claims?limit=1 HTTP/1.1" 200 OK
2026-09-29T06:48:20.761721552Z [policy] INFO:     10.244.1.70:48276 - "GET /policies?limit=1 HTTP/1.1" 200 OK
2026-09-29T06:48:20.772116344Z [product] INFO:     10.244.1.70:43152 - "GET /products?limit=1 HTTP/1.1" 200 OK
2026-09-29T06:48:28.581264417Z [claim] INFO:     10.244.1.70:59418 - "GET /claims?skip=0&limit=100 HTTP/1.1" 200 OK
2026-09-29T06:48:28.594391833Z [policy] INFO:     10.244.1.70:33032 - "GET /policies?skip=0&limit=100 HTTP/1.1" 200 OK
2026-09-29T06:48:28.606135000Z [policy] INFO:     10.244.1.70:33036 - "GET /policies?skip=100&limit=100 HTTP/1.1" 200 OK
2026-09-29T06:48:28.617310917Z [product] INFO:     10.244.1.70:49590 - "GET /products?skip=0&limit=100 HTTP/1.1" 200 OK
```

## I-3: Simulate a new premium

### Test description

Use the premium simulation Tool for a new auto policy, without referring to premiums on existing policies.

### Input

- Japanese: 「既存契約の保険料ではなく、新規の自動車保険PRD-002を1990-01-01生・補償額300万円で試算し、月額と年額を教えてください。」
- English: "Quote a new PRD-002 auto policy for a person born on 1990-01-01 with ¥3,000,000 coverage. Report the monthly and annual premium. Do not report premiums from existing policies."

### Expected processing

Call the premium simulation Tool with `product_id: PRD-002`, `birth_date: 1990-01-01`, and `sum_insured: 3000000`. The Japanese run used `insurance_search` → `insurance_get_schema` → `insurance_execute`. The English run used `insurance_list_tools` → `insurance_get_schema` → `insurance_execute`. **Whether to use search depends on the LLM.** The query passed to search in the Japanese run was not recorded in the evidence.

### Baseline

The quoted amount changes with age on the execution date, so there is no fixed expected value. The following is the **measured result for 2026-09-29**.

| Age | Monthly | Annual |
|---:|---:|---:|
| 36歳 | 4,580円 | 55,000円 |

### Output

Both the Japanese browser response and English direct API response reported age 36, monthly ¥4,580, and annual ¥55,000. Full English answer: `docs/evidence/insurance-2026-09-29/I-3-en-answer.md`. There is no screenshot of the English run. In a separate check, Opus called the premium simulation Tool directly from MCP `execute` with the same arguments and returned `monthly_premium: 4580`, `annual_premium: 55000`, `age: 36`, and `base_annual: 55000`. The upstream received one `POST /simulations`; there was no policy creation `POST /policies`.

### Screenshot

![I-3 Japanese Chat UI result](assets/images/chat-ui-insurance-i3-premium-simulation.png)

### Logs

Tool call order (`toolCalls`): Japanese `insurance_search` → `insurance_get_schema` → `insurance_execute`. English `insurance_list_tools` → `insurance_get_schema` → `insurance_execute`.

**Generated code and result from the final `execute`** (excerpt from `docs/evidence/insurance-2026-09-29/I-3-ja-mcp-server.log`):

```text
# execute 1/1（ログへの出力時刻は次のリクエスト到着時。Code Modeのrunnerは1リクエスト遅れて書き出す）
2026-09-29T06:50:02.489439502Z ============================================================
2026-09-29T06:50:02.489442793Z CODE MODE — Generated Python:
2026-09-29T06:50:02.489445752Z ============================================================
2026-09-29T06:50:02.489447168Z res = await call_tool('property_dash_insurance_dash_premium_dash_simulation_dash_api_simulate_simulations_post', {
2026-09-29T06:50:02.489448543Z     'birth_date': '1990-01-01',
2026-09-29T06:50:02.489449668Z     'product_id': 'PRD-002',
2026-09-29T06:50:02.489450793Z     'sum_insured': 3000000
2026-09-29T06:50:02.489451918Z })
2026-09-29T06:50:02.489452960Z return res
2026-09-29T06:50:02.489454168Z ============================================================
2026-09-29T06:50:02.489455418Z Available tools: ['call_tool']
2026-09-29T06:50:02.489457793Z Result: {'product_id': 'PRD-002', 'product_name': '自動車保険「ドライブセーフ」', 'category': '自動車保険', 'age': 36, 'sum_insured': 3000000, 'monthly_premium': 4580, 'annual_premium': 55000, 'breakdown': {'base_annual': 55000, 'variable_annual': 0, 'smoker_surcharge': 0, 'age_factor': 1.0}}
```

**Upstream Insurance API access logs** (Japanese run; excerpt from `docs/evidence/insurance-2026-09-29/I-3-ja-insurance-api.log`):

```text
2026-09-29T06:49:45.619513883Z [simulation] INFO:     10.244.1.70:56102 - "POST /simulations HTTP/1.1" 200 OK
```

## Notes on search

Measured results from searches sent directly to MCP on 2026-09-29. The spec summaries / descriptions are registered in English.

| Query | Matches | Top result / observation |
|---|---:|---|
| `申込一覧の取得` | 0 | No hit for Japanese query |
| `list applications` | 9 | `list_applications` ranked first |
| `premium quote` | 7 | Premium simulation (`simulate`) ranked first |
| `underwriting` | 2 | English words in descriptions can match even when absent from Tool names |
| `insurance products` | 32 | Every Tool matched because Source names contain `insurance`; does not narrow results |

## Imports in execute

The same results were confirmed on both MCP Servers on 2026-09-29.

| Result | Modules |
|---|---|
| Success | `asyncio`, `json`, `math`, `re`, `datetime` |
| `ModuleNotFoundError` | `collections`, `statistics` |

## Verification method notes

- Upstream access logs were captured from each Insurance Pod using `kubectl logs --timestamps`, excluding `/health`. Runner generated code and `Result:` were captured the same way.
- The runner writes generated code and `Result:` **one request late**. The displayed timestamp is when the next request arrived, so assign records to cases using the `toolCalls` order in `docs/evidence/insurance-2026-09-29/chat-ui-chat_completed.log`.
- No write operations were performed. The registered OpenAPI specs include update and delete Tools too, so the demo is limited to reading and simulations that do not change data. To restore seed data, run `kubectl -n insurance rollout restart deploy`.
- Do not include customer personal information (names, values resembling My Number identifiers, addresses, or phone numbers) in answers or public log excerpts.
