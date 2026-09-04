# 0001. mock-api の公開方式（Service type / Macからの到達方式）

- **日付**: 2026-09-04（事後再構成。判断自体は2026-08〜09初頭の作業で下された）
- **状態**: 決定

## コンテキスト
mock-api（気温データAPI）をMinikube上にデプロイし、(a) クラスタ内のKong DPから、
(b) 検証用にMacホストから、の両方で到達可能にする必要がある。macOS + docker driverでは
ノードがDocker Desktop VM内で動くため、`192.168.49.0/24`のようなクラスタ内部アドレスに
Macから直接ルーティングできない制約がある。

## 検討した選択肢
1. **LoadBalancer (MetalLB)**: `minikube addons enable metallb`でEXTERNAL-IPを払い出す。
   実装当初はこれを採用したが、上記のdocker driver制約によりEXTERNAL-IPがMacから到達不可と
   判明（ping・curlいずれも失敗）。クラスタ内からは到達可能なため無意味ではないが、
   Mac側の検証には別手段が必要だった。
2. **ClusterIP + `kubectl port-forward`**: mock-api単体の直接ヘルスチェック用。固定ポート
   `8088`にport-forwardする。シンプルで確実に動くが、Kong DP経由の本番相当ルートは検証できない。
3. **ClusterIP + `minikube tunnel`（Kong DP経由）**: mock-apiはKong DP内部からのみ直接到達
   （Service DNS）とし、Mac側はKong DPのLoadBalancer Serviceを`minikube tunnel`で公開し、
   `KongRoute /mock-api`経由でアクセスする。**注意（2026-09-04訂正）**: これはmock-apiへの
   直接到達性を確認するためのデバッグ用ルートであり、AIエージェントが実際に接続するデモ本体の
   MCPエンドポイント（Konnect UI上でMCP Server定義後に確定する`/mcp/<name>`形式のルート）とは
   別物。当初「デモの実際のクエリ経路を再現できる」と記載していたが不正確だったため訂正した
   （詳細: `docs/design-brief.md`3章）。

## 決定
mock-api本体は選択肢2（ClusterIP + port-forward、直接ヘルスチェック用）を採用しつつ、
本番相当のクエリ経路検証は選択肢3（`minikube tunnel` + KongRoute）を追加する方針とした。
選択肢1（MetalLB）は撤去した。

## 判断基準・根拠
- MetalLBはdocker driver環境のMacからは原理的に到達不可なため、Mac側検証という目的に対しては
  無意味（クラスタ内到達性はClusterIPでも変わらず確保できる）
- mock-api単体の素早いヘルスチェックにはport-forwardが最も単純で確実
- デモの実際の経路（Kong DP経由）を検証するには、Kong DP自体をMacから到達可能にする必要があり、
  そのための標準的な手段が`minikube tunnel`（MetalLBとは別のminikube機能）

## 想定していたこと vs 実際どうだったか
- 想定: `minikube tunnel`はLoadBalancer ServiceにMacから到達可能なexternal-ipを割り当てる
- 実際（2026-09-04検証）: 想定通り。`minikube tunnel`実行後、`dataplane-ingress-dataplane-*`
  のEXTERNAL-IPが`127.0.0.1`で到達可能になり、`curl http://localhost/mock-api/health`が
  Kong経由（`X-Kong-Upstream-Latency`ヘッダー確認）で200を返した。MetalLBと異なり、
  docker driver環境の制約を受けなかった
- 追加で判明した点: `minikube tunnel`は80/443番ポートのバインドに対話的な`sudo`パスワード
  入力を要求するため、エージェントの非対話シェル（バックグラウンド実行）からは起動を
  完了できない。利用者本人がターミナルで直接実行する必要がある（`deploy/README.md`に注記済み）

## 影響・トレードオフ
- mock-api単体検証（port-forward）とKong DP経由検証（tunnel）の2系統の到達方式が併存し、
  `deploy/README.md`が若干複雑になった
- `minikube tunnel`は対話的なsudo入力が前提のため、エージェント単独では完結できず、
  利用者の手動実行（常駐）を要する運用上の制約がある

## 関連する決定
- [0003-repo-consolidation](0003-repo-consolidation.md)（本デモの実運用手順の一本化）
