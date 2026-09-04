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
（未実施。Chat UI実装後にこのセクションを更新する）

## 影響・トレードオフ
- Next.js/Vercel AI SDKという比較的重量級な技術選択になる（`kong-secure-rag`のVite+Reactより
  セットアップ・依存関係が多い）。ただしMCP接続が本デモの核心機能である以上、必要なコスト
- パッケージバージョンは`kong-azure-obo-demo`時点（`ai`v7.0.87等）に追随するか、実装時点の
  最新版を使うかは実装時に判断する（Vercel AI SDKは破壊的変更が比較的頻繁な点に留意）

## 関連する決定
- [0003-repo-consolidation](0003-repo-consolidation.md)
