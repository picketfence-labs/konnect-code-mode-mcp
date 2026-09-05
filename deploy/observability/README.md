# ログ基盤（Grafana Loki + Promtail）デプロイ手順

mock-api・MCP Server・chat-ui のログを集約するログ基盤。技術選定・方針の背景は
[ADR-0006](../../docs/decisions/0006-log-observability-stack.md)を参照。

## 構成

```mermaid
flowchart LR
  subgraph Pods["各Namespaceのコンテナ"]
    chatui["chat-ui\n(demo ns)\n構造化JSONログ<br/>onEnd: usage/steps/toolCalls"]
    mcp["MCP Server\n(default ns)\nCode Mode生成コード・\ncall_tool結果の非構造化ログ<br/>（app.pyはこのリポジトリから変更不可）"]
    mockapi["mock-api\n(demo ns)"]
  end
  subgraph obs["observability namespace"]
    promtail["Promtail\n(DaemonSet)"]
    loki["Loki"]
    grafana["Grafana"]
  end
  chatui -->|stdout| promtail
  mcp -->|stdout| promtail
  mockapi -->|stdout| promtail
  promtail --> loki
  grafana -->|LogQL| loki
```

- **chat-ui**: 自分たちで書いているコード（`chat-ui/app/api/chat/route.ts`）の
  `streamText`の`onEnd`コールバックで、リクエストごとに`{event: "chat_completed",
  usage, stepCount, toolCallCount, toolCalls, finishReason}`という構造化JSON 1行を
  stdoutへ出力する。token使用量・tool呼び出し回数をLogQLで直接集計できる
- **MCP Server**: `app.py`はKonnect Control Planeが生成しPod起動時に取得するため
  このリポジトリから変更できない（[ADR-0006](../../docs/decisions/0006-log-observability-stack.md)
  参照）。追加の計装は行わず、Code Mode自体が出力する非構造化ログ（生成Pythonコード・
  `call_tool`結果等）をそのまま収集する
- Promtailは全namespaceのPod stdoutを自動収集するDaemonSetのため、mock-api等
  追加設定なしで収集対象に含まれる

## 前提

- Minikube稼働中、`kubectl`がクラスタに接続済み
- Helmリポジトリ`grafana`が登録済み（`helm repo add grafana https://grafana.github.io/helm-charts`）
- mock-api・chat-uiと同じ方式（Kong DP + `minikube tunnel`）でGrafanaにアクセスするため、
  別ターミナルで`minikube tunnel`を常駐させておく（手順は[deploy/README.md](../README.md)
  「Kong DP をMacから到達可能にする」参照。既に起動済みなら再実行不要）

## 手順

### 1. Loki + Promtail + Grafana のデプロイ

`grafana/loki-stack`（Deprecated表示だが実運用に問題なし。Loki公式は後継として
`k8s-monitoring`chartを推奨しているが、本デモ規模では`loki-stack`で十分）を
1リリースでまとめてデプロイする。

Grafana単体はNext.jsのようなbasePath設定を持たないが、代わりに標準のリバースプロキシ
配下運用機能（`server.root_url` / `server.serve_from_sub_path`）を持つため、これを
`/grafana`向けに有効化しておく（考え方はchat-uiの`basePath`と同じ。参照:
[ADR-0007](../../docs/decisions/0007-chat-ui-kong-route-exposure.md)、
[Grafana公式: Run Grafana behind a reverse proxy](https://grafana.com/tutorials/run-grafana-behind-a-proxy/)）。

```bash
helm repo add grafana https://grafana.github.io/helm-charts   # 未登録の場合のみ
helm repo update

helm upgrade --install loki grafana/loki-stack \
  -n observability --create-namespace \
  --set grafana.enabled=true \
  --set promtail.enabled=true \
  --set loki.persistence.enabled=false \
  --set grafana."grafana\.ini".server.root_url="%(protocol)s://%(domain)s/grafana/" \
  --set grafana."grafana\.ini".server.serve_from_sub_path=true
```

`loki.persistence.enabled=false`はデモ用の簡易構成（Pod再作成でログが消える）。
永続化したい場合は`--set loki.persistence.enabled=true`と適切な`storageClassName`を指定する。

### 2. Grafana を Kong DP 経由で公開する

mock-api・chat-uiと同じ`KongService`/`KongRoute`パターン（strip_pathなし。
上記の`serve_from_sub_path`とセットで機能する。詳細はファイル内コメント参照）で
`/grafana`に公開する。

```bash
kubectl apply -f ../kong/grafana-kong.yaml
```

### 3. Grafana へのアクセス

```bash
kubectl -n observability get secret loki-grafana \
  -o jsonpath='{.data.admin-password}' | base64 -d; echo

# ブラウザで http://localhost/grafana （user: admin / 上記コマンドで取得したpassword）
```

**検証済み（2026-09-05）**: `curl http://localhost/grafana/login`・`/grafana/api/health`・
`/grafana/public/build/*.{css,js}` がいずれもKong経由で200 OKになることを確認
（`<base href="/grafana/" />`によりアセットも相対パスで正しく解決される）。

Grafana起動時に`Loki`データソースが自動登録されている（chart既定）。
「Explore」から下記のようなLogQLでログを横断検索できる。

```logql
# chat-uiの構造化ログ（token使用量・tool呼び出し回数）
{namespace="demo", app="chat-ui"} |= "chat_completed" | json

# MCP Serverのtool呼び出しログ（Code Mode生成コード・実行結果）
{namespace="default", container="mcp-server"} |= "CODE MODE"
```

### 4. 動作確認（API経由、Grafana UIを開かずに確認する場合）

```bash
kubectl -n observability port-forward svc/loki 3100:3100 &

curl -s -G "http://localhost:3100/loki/api/v1/query_range" \
  --data-urlencode 'query={namespace="demo", app="chat-ui"} |= "chat_completed"' \
  --data-urlencode 'limit=5'
```

## 既知の制約

- **MCP Server側のログは非構造化**: `app.py`をこのリポジトリから変更できないため、
  tool呼び出し回数・ペイロードサイズの厳密な集計はLogQLの正規表現マッチに頼ることになる
  （[ADR-0006](../../docs/decisions/0006-log-observability-stack.md)参照）
- `loki.persistence.enabled=false`のため、`loki-0` Podが再作成されるとログ履歴は失われる
