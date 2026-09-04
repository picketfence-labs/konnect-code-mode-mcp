# Minikube デプロイ手順

mock-api（世界都市気温 API）を Minikube にデプロイする手順。
Service は `ClusterIP`。クラスタ内（Kong DP など）は Service DNS で参照し、
**mock-api 単体の直接ヘルスチェックは `kubectl port-forward`**（固定ポート `8088`）で行う。
デモ本番のクエリ経路（Kong DP 経由）は、後述の **`minikube tunnel`**（未検証）で
Mac から到達させる方針にした（`deploy/kong/mock-api-kong.yaml` の `KongRoute /mock-api` 参照）。

## ポート割当（固定）

| サービス | クラスタ内 | Mac ローカル |
|---|---|---|
| mock-api（直接） | Service `demo/mock-api` :80（→ Pod :8000） / DNS `mock-api.demo.svc.cluster.local` | port-forward: **`localhost:8088`** ← 固定。mock-api単体の疎通確認用 |
| Kong DP（proxy） | Service `dataplane-ingress-dataplane-*`（LoadBalancer、Kong Operator管理） | `minikube tunnel` 経由の LoadBalancer external-ip:80 → `http://localhost/mock-api`（KongRoute `strip_path`。**未検証**） |

## 前提

- Minikube 稼働中（driver=docker、macOS）
- `kubectl` がクラスタに接続済み

## 構成図

```mermaid
flowchart LR
  subgraph Mac["macOS ホスト"]
    curl["curl / ブラウザ / Claude Code"]
    pf["kubectl port-forward\n(localhost:8088, 常駐)"]
  end
  subgraph VM["Docker VM (minikube node)"]
    subgraph K8s["Kubernetes (ns: demo)"]
      svc["Service mock-api\ntype:ClusterIP\nmock-api.demo.svc"]
      pod["Pod mock-api:0.1.0\n:8000"]
      consumer["(将来) Kong DP\n→ svc DNS で参照"]
    end
  end
  curl -->|localhost:8088| pf
  pf -->|API server 経由| svc
  consumer -->|クラスタ内で到達| svc
  svc --> pod
```

> **macOS + docker driver の制約**: ノードが Docker Desktop の VM 内で動くため、
> クラスタ内ネットワークは Mac ホストから直接ルーティングできない。**Mac から手元で
> 叩く時は `kubectl port-forward`**（mock-api は固定 `8088`）を使う。クラスタ内
> （Kong DP → mock-api）は Service DNS `mock-api.demo.svc.cluster.local` で到達可能。

## 手順

### 1. mock-api イメージを minikube 内にビルド（外部レジストリ不要）

```bash
eval $(minikube docker-env)
docker build -t mock-api:0.1.0 mock-api/
eval $(minikube docker-env -u)   # 元の docker に戻す
```

### 2. デプロイ

```bash
kubectl apply -f deploy/mock-api/mock-api.yaml
kubectl -n demo rollout status deploy/mock-api
kubectl -n demo get svc mock-api
```

### 3. Mac から到達可能にする（別ターミナルで常駐）

```bash
kubectl -n demo port-forward svc/mock-api 8088:80
```

### 4. 疎通確認（Mac から、mock-api 単体）

```bash
curl http://localhost:8088/health
curl http://localhost:8088/cities | head -c 300
curl "http://localhost:8088/temperatures?city_id=1&month=3"
```

### 5. Kong DP をMacから到達可能にする（`minikube tunnel`、未検証）

デモ本番のクエリは mock-api に直接ではなく Kong DP → `KongRoute` 経由で通す想定。
`minikube tunnel` は LoadBalancer Service に到達可能な external-ip を割り当てる
minikube 標準機能で、MetalLB（撤去済み）とは別の仕組み。

```bash
# mock-api を Kong 経由で公開する KongService/KongRoute を適用
kubectl apply -f deploy/kong/mock-api-kong.yaml

# 別ターミナルで常駐（sudo を要求される場合あり。Ctrl-C で停止）
minikube tunnel

# Kong DP の LoadBalancer external-ip を確認
kubectl get svc -n default -l gateway-operator.konghq.com/dataplane-name -o wide
```

疎通確認（Mac から。パスは `KongRoute` の `paths: /mock-api` + `strip_path: true`）:

```bash
curl http://localhost/mock-api/health
```

**未検証**: `minikube tunnel` が docker driver 環境で実際に external-ip を Mac から
到達可能にできるかは次回実機で確認する（過去に MetalLB の EXTERNAL-IP がこの環境では
到達不可だった実績があるため、`minikube tunnel` も同様の制約を受けないか要確認）。

## 動作確認済みの状態

- `kubectl -n demo get pods` → `mock-api-*` が Running
- Mac から: `kubectl -n demo port-forward svc/mock-api 8088:80` 経由で到達可能
  （`{"status":"ok","cities":100,"temperatures":12000}`）
- クラスタ内から: `http://mock-api.demo.svc.cluster.local/health` で到達可能
  （Kong DP が使う経路。OpenAPI spec `servers[0]` に設定済み）
- Kong DP 経由（`minikube tunnel` + `KongRoute /mock-api`）: **未検証**（上記手順は方針のみ。次回のデプロイ時に実機で確認する）

## 片付け

```bash
kubectl delete -f deploy/mock-api/mock-api.yaml
# port-forward は Ctrl-C で停止
```
