# Insurance API のデプロイと Context Mesh 登録

## これは何か

このディレクトリには、すでに `insurance` namespace で稼働している6つの Insurance API を
再現する manifest の固定コピーがあります（方式 B'）。Control Plane / Data Plane は既存のものを
使い、新しい KongService / KongRoute は作成しません。決定の背景は
[ADR-0008](../../docs/decisions/0008-insurance-integration.md)を参照してください。

## 適用と確認

bundle の既定イメージタグ `v0.1.1` を指定した manifest です。現在のクラスタへ適用しても既存の
オブジェクトと一致する想定です。

```bash
kubectl diff -f deploy/insurance/services.yaml
kubectl apply -f deploy/insurance/services.yaml
kubectl -n insurance get pods
```

いずれかの API を Mac から直接確認する場合は、別ターミナルで port-forward を起動します。

```bash
kubectl -n insurance port-forward svc/product 8000:8000
```

```bash
curl http://localhost:8000/health
```

## Context Mesh に登録する OpenAPI 仕様

このデモでは、bundle の OpenAPI 仕様（v0.1.3、OpenAPI 3.1.0）を**そのまま**登録します。
v0.1.2 から、各仕様の `servers` はクラスタ内の Service DNS（`http://<svc>.insurance.svc.cluster.local:8000`）
になっているので、変更は不要です。手元の OpenAPI 仕様をそのまま登録するだけで MCP Server 化
できることが、このデモで示したい点です（[ADR-0008](../../docs/decisions/0008-insurance-integration.md)）。

| Source 名（仕様の `info.title` から） | bundle の仕様（v0.1.3） | 上流 URL（仕様の `servers`） | 操作数 |
|---|---|---|---:|
| `property-insurance-product-api` | [`services/product/openapi.yaml`](https://github.com/picketfence-labs/kong-api-bundle-insurance/blob/v0.1.3/services/product/openapi.yaml) | `http://product.insurance.svc.cluster.local:8000` | 6 |
| `property-insurance-customer-api` | [`services/customer/openapi.yaml`](https://github.com/picketfence-labs/kong-api-bundle-insurance/blob/v0.1.3/services/customer/openapi.yaml) | `http://customer.insurance.svc.cluster.local:8000` | 6 |
| `property-insurance-premium-simulation-api` | [`services/simulation/openapi.yaml`](https://github.com/picketfence-labs/kong-api-bundle-insurance/blob/v0.1.3/services/simulation/openapi.yaml) | `http://simulation.insurance.svc.cluster.local:8000` | 2 |
| `property-insurance-application-api` | [`services/application/openapi.yaml`](https://github.com/picketfence-labs/kong-api-bundle-insurance/blob/v0.1.3/services/application/openapi.yaml) | `http://application.insurance.svc.cluster.local:8000` | 6 |
| `property-insurance-policy-api` | [`services/policy/openapi.yaml`](https://github.com/picketfence-labs/kong-api-bundle-insurance/blob/v0.1.3/services/policy/openapi.yaml) | `http://policy.insurance.svc.cluster.local:8000` | 6 |
| `property-insurance-claim-api` | [`services/claim/openapi.yaml`](https://github.com/picketfence-labs/kong-api-bundle-insurance/blob/v0.1.3/services/claim/openapi.yaml) | `http://claim.insurance.svc.cluster.local:8000` | 6 |

v0.1.1 以前の仕様は `servers` が例示用のドメイン（`https://api.example.com/<svc>`）のままなので、
登録すると `execute` が上流に届きません。bundle をローカルに clone している場合は、v0.1.3 以降を
checkout してから貼り付けてください。登録した仕様の `servers` は、MCP Server が使う上流 URL の
既定値になります。

v0.1.3 では、summary と description がすべて英語になりました。Context Mesh の `search` は
英語の description も検索の対象にするため、Tool 名に無い単語（例: `underwriting`、`premium`）でも
目的の Tool が見つかります（下の「注意事項」）。

Pod のイメージは `v0.1.1` のままです。v0.1.1 から v0.1.3 までの `services/` 配下の変更は、
OpenAPI 仕様と、API の説明文（summary、description、パラメータの説明）だけで、パラメータや
制約は変わっていません。

## Konnect UI への登録

以下は [INSTRUCTIONS.md §2](../../INSTRUCTIONS.md) と同じ順序（MCP Server の作成 → API Source
の登録 → Data Plane の選択）で行う登録手順です。

1. Konnect UI の **Context Mesh** で **MCP Server** を新規作成し、名前を `kong-insurance` にします。
2. 接続先の API として、上の表の6つの API Source を一つずつ登録します。bundle の仕様（v0.1.3）を
   そのまま貼り付けます。
3. Data Plane には、World Weather MCP Server と同じ既存の Data Plane を選択します。新しい
   Control Plane は作成しません。
4. 保存後、MCP Server の概要画面で状態とツール一覧を確認します。

MCP URL は `http://127.0.0.1/mcp/kong-insurance` です（`minikube tunnel` 経由）。

### 登録後に確認・記録する項目

- `tools/list` に表示されるのは `list_tools` / `search` / `get_schema` / `execute` の4つ
- `list_tools` で見える API の Tool は**32個**（Source ごとに 6 / 6 / 2 / 6 / 6 / 6）。
  Tool 名は `<Source名>_<operationId>` の形で、Source 名の `-` は `_dash_` に置き換わる
  （例: `property_dash_insurance_dash_product_dash_api_list_products_products_get`）
- MCP Server の health status
- list 系の Tool は `{total, items}` を返し、`skip` / `limit` でページングする（`limit` の最大値は100）

## 注意事項

- **書き込み系の操作も公開されます。** bundle の仕様をそのまま登録するため、各 API の登録・更新・
  削除（POST / PUT / DELETE）も Tool になります。デモでは Chat UI の指示で参照と試算だけに
  限定します。データは各 Pod のメモリに保持されているので、書き換わった場合は再起動すると
  seed の状態に戻ります。

  ```bash
  kubectl -n insurance rollout restart deploy
  ```

- 顧客データは架空ですが、マイナンバーに似た値を含みます。デモ回答に個別の顧客行を出力しないで
  ください。
- Code Mode の `execute` で動く Python では、標準ライブラリの一部が import できません
  （2026-09-29 の観測。`collections`、`statistics` は `ModuleNotFoundError`。`asyncio`、`json`、`math`、
  `re`、`datetime` は成功。World Weather と `kong-insurance` の両方で同じ結果）。集計は組み込みの
  機能だけで書きます。
- `search` は日本語のクエリではヒットしません（2026-09-29 時点の観測）。検索の対象は Tool 名と
  英語の description で、単語単位の完全一致です。英単語で検索します（例: `list applications`、
  `premium quote`、`paid claims`）。Source 名が `property-insurance-` で始まるため、`insurance` や
  `property` はすべての Tool に当たり、絞り込みには役立ちません。
