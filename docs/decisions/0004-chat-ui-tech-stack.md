# 0004. Chat UIの技術スタック選択

- **日付**: 2026-09-04
- **状態**: 決定

## コンテキスト
現状、デモへのアクセスはClaude Code CLIの`mcp add`経由のみで、一般向けに見せられるChat UIが
無い（`docs/design-brief.md`2章「将来」5番目）。利用者は技術スタックに特に好みが無いとして、
過去に構築した2つの参考実装（`kong-secure-rag`、`kong-azure-obo-demo`）を参照するよう指示した。

## 検討した選択肢
両リポジトリのChat UI実装をローカルクローンで調査した結果:

1. **`kong-secure-rag/ui/`のパターン**: Vite 5 + React 18、UIライブラリ無し（素のTailwind CSS
   3系）。LLM/MCP接続ライブラリは使用せず、`fetch()`でKong Gateway（OpenAI互換chat completion
   エンドポイント）へ非ストリーミングでPOSTするだけの薄い実装。MCPクライアント機能は無い
   （バックエンド側の関心として分離されている）
2. **`kong-azure-obo-demo/services/chat-ui/`のパターン**: Next.js 16 (App Router) + React 19、
   Tailwind CSS 4系。`ai`(v7.0.87) + `@ai-sdk/openai`(v4.0.53) + `@ai-sdk/react`(v4.0.90)の
   Vercel AI SDKで`useChat`フックを使用。**`@ai-sdk/mcp`の`createMCPClient`でMCPサーバーに
   Streamable HTTP接続**（`transport: {type: "http", url, headers}`）し、`tools/list`→
   `tools/call`のJSON-RPCをエージェントのツール呼び出しとして扱う。認証はエージェント自身が
   持たず、上流（今回はKong経由ではなく直接ヘッダー指定）から受け取ったトークンをそのまま
   MCPサーバーへ再提示する設計

## 決定
選択肢2（`kong-azure-obo-demo/services/chat-ui/`のパターン: Next.js + Vercel AI SDK + MCP
client）を採用する。

## 判断基準・根拠
- 本デモの主目的はMCPサーバー（Context Mesh経由で生成されたFastMCPサーバー）への接続と
  ツール呼び出しの可視化であり、`kong-secure-rag`パターン（MCP機能を使わない素のchat
  completion）ではこの核心を全く見せられない
- `kong-azure-obo-demo`のパターンは`@ai-sdk/mcp`の`createMCPClient`によるMCP接続が実機検証済み
  （`initialize`→`notifications/initialized`→`tools/list`→`tools/call`が正常動作することを
  確認済み、[[../../../02-Areas/Konnect - Context Mesh|Kong Gateway OIDC OBO実装での実地検証]]）
- 本デモでは`kong-azure-obo-demo`のようなOIDC OBO（Kongが検証したトークンをそのまま再提示する
  構成）は不要（現状はKonnect UIでMCP Serverを直接定義し、`X-Upstream-Api-Key`/
  `X-Upstream-Bearer-Token`ヘッダーで上流APIキーを渡す方式、CLAUDE.md「主要な制約」節参照）。
  MCPサーバーへの接続時にこれらのヘッダーをそのまま渡す形にすれば、認証部分を簡略化して
  Vercel AI SDK部分のパターンだけ再利用できる
- `kong-secure-rag`のUI実装（コンポーネント分割・Tailwindの使い方）はレイアウトの参考程度に
  留める

## 想定していたこと vs 実際どうだったか
- 想定: LLMプロバイダはkong-azure-obo-demo同様OpenAI（`@ai-sdk/openai`）
- 実際（2026-09-04実装時）: 利用者の指示でGemini（`@ai-sdk/google`）に変更。APIキー命名は
  Google系の別参考実装`kong-secure-rag`の`.env.example`規約（`GEMINI_API_KEY`/`GEMINI_MODEL`）
  に合わせた。キーはコードに含めず、ローカルは`.env.local`、Minikube上はK8s Secret
  （`chat-ui-secrets`、`envFrom.secretRef`）で注入する構成にした
- 想定: デプロイ形態は未定（ローカル`next dev`のみか、コンテナ化かは実装時に判断としていた）
- 実際: 利用者の指示でMinikube上にコンテナ化してデプロイする方針に決定。`mock-api`と同じ
  パターン（`eval $(minikube docker-env)` + `docker build` + `deploy/chat-ui/chat-ui.yaml`）
  を採用。Chat UIはPodとしてクラスタ内で稼働するため、**`minikube tunnel`に依存せず
  Kong DPの内部Service DNS**（`dataplane-ingress-dataplane-*.default.svc.cluster.local`）
  で直接MCPサーバーへ到達させた（Mac側のブラウザアクセスのみ`kubectl port-forward`）。
  この構成で実機（`kubectl apply`後のPod）から実際に「過去10年の3月の平均気温Top5」等の
  クエリを送信し、Code Mode経由（`search`→`get_schema`→`execute`）で正しい集計結果が
  返ることを確認した
- 想定外の追加発見: `@ai-sdk/mcp`経由のツールはUIMessageの`type: 'dynamic-tool'`
  （静的ツールの`'tool-<name>'`とは別の型）でクライアントに届く。`ai`v7の`streamText`は
  既定で1ステップしかツール呼び出しを継続しないため、`stopWhen: stepCountIs(10)`が
  必須だった（無いと最初のツール呼び出し結果だけでストリームが終わり、最終テキスト回答が
  生成されない）

## 影響・トレードオフ
- Next.js/Vercel AI SDKという比較的重量級な技術選択になる（`kong-secure-rag`のVite+Reactより
  セットアップ・依存関係が多い）。ただしMCP接続が本デモの核心機能である以上、必要なコスト
- パッケージバージョンは実装時点（2026-09-04）のnpm最新版で揃えた:
  `ai@7.0.92` / `@ai-sdk/react@4.0.95` / `@ai-sdk/google@4.0.63` / `@ai-sdk/mcp@2.0.44`
  （いずれも`@ai-sdk/provider@4.0.10`・`@ai-sdk/provider-utils@5.0.36`に揃っており相互互換）。
  `next@16.3.4` + `react@19.2.8`
- LLMプロバイダがGemini固定になったため、OpenAI等へ切り替える場合は`route.ts`の
  モデル生成部分（`@ai-sdk/google`の`createGoogleGenerativeAI`呼び出し）を差し替える必要がある

## 関連する決定
- [0003-repo-consolidation](0003-repo-consolidation.md)
