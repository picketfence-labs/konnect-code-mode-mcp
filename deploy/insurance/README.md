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

## OpenAPI 仕様の再生成

読み取り専用の参照元 `kong-api-bundle-insurance` のルートを指定します。スクリプトは Python 3
標準ライブラリと `yq` CLI を使い、6つの Source 用 JSON を生成します。

```bash
python3 scripts/build_insurance_specs.py --bundle-root /path/to/kong-api-bundle-insurance
python3 scripts/build_insurance_specs.py --check --bundle-root /path/to/kong-api-bundle-insurance
```

bundle の更新は自動追従せず、変更内容を確認した PR で仕様と必要な manifest を明示的に更新します。

## Konnect UI への登録

以下は [INSTRUCTIONS.md §2](../../INSTRUCTIONS.md) と同じ順序（MCP Server の作成 → API Source
の登録 → Data Plane の選択）で行う登録手順です。

1. Konnect UI の **Context Mesh** で **MCP Server** を新規作成し、名前を `kong-insurance` にします。
2. 接続先の API として、次の6つの API Source を一つずつ登録します。各 Source に対応する
   JSON ファイルの内容を UI の OpenAPI 入力欄へ貼り付けます。

| Source 名 | ファイル | 操作数 |
|---|---|---:|
| `insurance-product` | `insurance/openapi/product.json` | 2 |
| `insurance-customer` | `insurance/openapi/customer.json` | 2 |
| `insurance-simulation` | `insurance/openapi/simulation.json` | 1 |
| `insurance-application` | `insurance/openapi/application.json` | 2 |
| `insurance-policy` | `insurance/openapi/policy.json` | 2 |
| `insurance-claim` | `insurance/openapi/claim.json` | 2 |

3. Data Plane には、World Weather MCP Server と同じ既存の Data Plane を選択します。新しい
   Control Plane は作成しません。
4. 保存後、MCP Server の概要画面で状態とツール一覧を確認します。

### 登録後に記録する項目

- MCP URL
- `tools/list` に表示されたツール名
- Source ごとの操作数: 2 / 2 / 1 / 2 / 2 / 2（合計11）
- MCP Server の health status
- いずれかの list 呼び出しの応答形。`{total, items}` を返し、`skip` / `limit` でページングする。
  `limit` の最大値は100。

顧客データは架空ですが、マイナンバーに似た値を含みます。デモ回答に個別の顧客行を出力しないで
ください。
