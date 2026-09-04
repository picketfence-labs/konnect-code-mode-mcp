# Kong Operator + Konnect 接続 デプロイ手順

Minikube 上に Kong Operator をインストールし、Konnect Control Plane / DataPlane を接続する手順。
社内SE手順書（`Kong Operator Context Mesh - SE's.md`、Obsidian Vault管理）と
`~/LOCAL_REPO/context-mesh`（reference clone、**変更禁止**）を起点としていた実運用手順を、
本リポジトリに一本化したもの（[ADR-0003](../../docs/decisions/0003-repo-consolidation.md)）。

**役割分担**（[CLAUDE.md](../../CLAUDE.md)）: 本手順のうち Kubernetes/Helm 操作（Step 0〜3）は
エージェントが実行可。Konnect UI 上での MCP Server 作成・ステータス確認（Step 4）は
**利用者（Shinichi）が確認しながら進める**——エージェントは Konnect UI を直接操作しない。

## 前提

- Minikube 稼働中（driver=docker、macOS）、`kubectl` がクラスタに接続済み
- Konnect Personal Access Token（KPAT）を取得済み。**絶対にファイル・コミット・ログに残さない**
  （下記はすべて環境変数 `${KPAT}` 経由で渡す）

## Step 0. Helm リポジトリの準備

```bash
helm repo add kong https://charts.konghq.com   # 未登録の場合のみ
helm repo update
```

## Step 1. Kong Operator のインストール/アップグレード

```bash
helm upgrade --install kong-operator kong/kong-operator \
  --version 1.4.0 \
  -n kong-system --create-namespace \
  --set image.repository=docker.io/kong/nightly-kong-operator \
  --set-string image.tag=20260904 \
  --set env.FEATURE_GATES=mcp-server \
  --set env.ENABLE_CONTROLLER_KONNECT=true
```

⚠️ **`image.tag` は必ず `--set-string` で渡す**（`--set` だと `20260904` のような数値形式の
文字列が int64 に誤変換され、`InvalidImageName` で Pod が永久に Crash し、`--wait` が
無関係な `client rate limiter Wait returned an error: context deadline exceeded` で
タイムアウトする。詳細:
[troubleshooting-log.md](../../docs/troubleshooting-log.md)「Helm `--set` の数値型誤変換」）。

`image.tag=20260904` は 2026-09-04 時点の最新 nightly（[ADR-0005](../../docs/decisions/0005-kong-operator-image-tag-upgrade.md)
でKonnect側のステータス確認不可バグの解消を検証済み）。以後の新しい nightly タグに追随する場合も
同様に `--set-string` を使うこと。

確認:

```bash
kubectl -n kong-system rollout status deploy/kong-operator-kong-operator-controller-manager
```

## Step 2. Konnect Control Plane / DataPlane の接続

```bash
export KPAT=kpat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
envsubst < deploy/kong-operator/konnect-resources.yaml.template | kubectl apply -f -
```

`konnect-resources.yaml.template` の内容（[konnect-resources.yaml.template](konnect-resources.yaml.template)）:

- `KonnectAPIAuthConfiguration`: KPAT を Secret 的に保持（`spec.token` は平文管理だが
  Kubernetes Secret ではなく専用 CRD。クラスタ外に持ち出さないこと）
- `KonnectGatewayControlPlane`（名前 `test`）: Konnect 上に Control Plane
  `context-mesh-demo` を作成
- `KonnectExtension`（名前 `my-konnect-config`）: 上記 Control Plane への接続設定
- `DataPlane`（名前 `dataplane`）: `kong/kong-gateway:3.15`、replicas 1
  （社内SE手順書は `3.14` / replicas 3 だったが、本リポジトリでの実機確認では
  `3.15` / replicas 1 で Ready・Konnect UI 上も Healthy）

## Step 3. DataPlane の Ready 確認

```bash
kubectl wait --timeout=3m dataplane dataplane --for=condition=Ready
kubectl get dataplane dataplane -o jsonpath='{.status.conditions}'
```

## Step 4. MCP Server の作成（Konnect UI、利用者が実施）

以降は Konnect UI 上の操作（エージェントは実行しない。手順のみ提示し、利用者に確認を仰ぐ）:

1. Konnect UI で「Create new MCP Server」を選択
2. Add Existing API → OpenAPI spec をアップロード（本デモでは
   [mock-api/openapi.json](../../mock-api/openapi.json)）
3. Step 1〜3 で作成した Control Plane（`context-mesh-demo`）を選択
4. MCP Server の Status が **Healthy** になることを確認

デプロイ後、Context Mesh のランタイムは Kong DP 上のルート `/mcp/<mcp-server-name>` で
公開される。

## 動作確認済みの状態（2026-09-04）

- `helm -n kong-system list` → `kong-operator` が `deployed`、chart
  `kong-operator-1.4.0`、image tag `20260904`
- `kubectl get dataplane dataplane` → `Ready: True`
- `kubectl get konnectgatewaycontrolplane test` → `Programmed: True`
- Konnect UI 上で既存の MCP Server「world-monthly-temperature」が Status: Healthy
  （利用者が実機確認。[ADR-0005](../../docs/decisions/0005-kong-operator-image-tag-upgrade.md)）

## 片付け

```bash
kubectl delete -f <(envsubst < deploy/kong-operator/konnect-resources.yaml.template)
helm -n kong-system uninstall kong-operator
```

Konnect UI 側の Control Plane / MCP Server の削除は利用者が UI から行う。
