# 0006. ログ基盤の技術選定（Grafana Loki + Promtail、AI/MCP評価は構造化ログで対応）

- **日付**: 2026-09-04
- **状態**: 決定

## コンテキスト
`docs/design-brief.md`2章の要件6（将来項目）として、mock-api・MCP Serverのログを
現状のコンテナログ直接参照（`kubectl logs`）から集約・検証しやすい基盤に移行する必要が
あった。技術選定は当初未定で、「Grafana/Loki、またはAI/MCP評価に向いたログ基盤」という
2方向が併記されていた。

## 検討した選択肢
利用者に確認した結果、まず方向性として「AI/MCP評価特化型」（Code Modeによるトークン削減
効果——tool呼び出し回数・レスポンスサイズ等——を可視化する）を選ぶという判断があった。
これを具体化する手段として3案を比較した。

1. **Langfuse（自己ホスト）**: LLMトレース・token量・tool呼び出しを本格的に可視化できる
   最も機能が豊富な選択肢。ただし自己ホストにPostgres・ClickHouse・Redis・S3互換ストレージ
   （MinIO等）が必要で、Minikubeデモ環境に対して構築コスト・リソース負荷が最も重い
2. **Arize Phoenix（単一コンテナ）**: OpenTelemetry/OpenInference準拠のトレースを受け付ける
   軽量なLLM Observability専用UI。ただしVercel AI SDK（本リポジトリのchat-uiが使用）との
   公式連携実績が薄く、OTel計装から自前で組む検証コストが読めない
3. **構造化ログ + Grafana Loki + Promtail**: 新規のトレース専用基盤は導入せず、
   (a) chat-ui（`app/api/chat/route.ts`、自分たちで書いているコード）の`onFinish`で
   LLMのtoken使用量・step数を構造化JSONとしてstdoutに出力し、(b) MCP Server
   （Konnect Control Planeが生成し起動時に取得する`app.py`。**このリポジトリでは変更不可**、
   後述）の既存の（非構造化だが情報量の多い）stdoutログをそのまま収集する。
   Promtailが全PodのコンテナログをそのままLokiに集約し、Grafana Explore / LogQLで
   横断検索・可視化する

## 制約: MCP Server側（`app.py`）はこのリポジトリから変更できない
調査の過程で判明した重要な制約。MCP Serverの実体（`app.py`）はKonnect Control Planeが
`oas-to-python`で生成し、Podの`init-container`が起動時に`/code`エンドポイントから取得する
（[CODE_MODE.md](../../CODE_MODE.md)参照）。つまり**本リポジトリのコードとしては存在せず、
デプロイのたびにControl Planeから再取得される**ため、tool呼び出し回数やペイロードサイズを
構造化ログとして出力するような改修をこのリポジトリ側から加えることはできない。

ただし実機確認の結果、Code Mode自体が生成コード・`call_tool`呼び出し名・実行結果
（`Result: {...}`）をかなり詳細にstdoutへ出力していることを確認済み
（`kubectl logs <mcp-server pod>`で実際に確認、2026-09-04）。この既存ログは非構造化だが
情報量は十分にあり、LogQLの正規表現フィルタで「生データ件数」と「最終`Result:`のサイズ」を
比較する形であれば、Code Modeによる削減効果の可視化にそのまま使える。

## 決定
選択肢3（構造化ログ + Grafana Loki + Promtail）を採用する。

- 新規インフラ: `grafana/loki-stack` Helm chart（Loki + Promtail + Grafana、単一リリース）
  を`observability` namespaceにデプロイ
- chat-ui側: `streamText`の`onFinish`コールバックで、リクエストごとに
  `{event: "chat_completed", usage, steps, ...}`という構造化JSON 1行をstdoutへ出力する
  （Promtailが自動収集、コード変更のみで新規サイドカー等は不要）
- MCP Server側: 追加の計装は行わず、既存の`CODE MODE`ログをそのままLokiに集約する

## 判断基準・根拠
- 利用者の判断: 「AI/MCP評価特化型」の方向性は望むが、Langfuseの自己ホスト運用コスト
  （Postgres/ClickHouse/Redis/MinIO）はMinikubeデモには過大と判断
- Arize Phoenixは軽量だがVercel AI SDKとの連携実績が薄く、検証コストが読めない
- 自分たちで書いているコード（chat-ui）には構造化ログを、書いていないコード
  （MCP Server生成コード）には既存ログの収集のみを充てる、という責務分界が
  「変更できないものを変更しようとしない」という制約に自然に合致する
- Loki/PromtailはMinikubeノードの現在の負荷（12%request/55%limit、2026-09-04時点）に
  対して軽量で、リソース面のリスクが小さい

## 想定していたこと vs 実際どうだったか
- 想定: MCP Server側にもtool呼び出し回数・ペイロードサイズを構造化ログとして仕込む前提で
  検討を始めていた
- 実際: `app.py`がControl Plane生成・起動時取得のためこのリポジトリから変更できないと判明
  （[CODE_MODE.md](../../CODE_MODE.md)のアーキテクチャ確認で発覚）。既存の非構造化ログの
  収集のみに方針転換した。詳細は[troubleshooting-log.md](../troubleshooting-log.md)

## 影響・トレードオフ
- MCP Server側のログはLogQLでの文字列マッチ・正規表現に頼ることになり、
  chat-ui側ほど厳密な集計はできない（トレードオフとして許容）
- 将来Context MeshがGA後にMCP Serverの計装オプションを提供するようになれば、
  再評価の余地がある

## 関連する決定
- [0004-chat-ui-tech-stack](0004-chat-ui-tech-stack.md)
