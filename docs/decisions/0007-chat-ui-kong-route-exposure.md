# 0007. chat-ui のKong DP経由公開方式（ホストベース vs パスベース + basePath）

- **日付**: 2026-09-05
- **状態**: 決定

## コンテキスト

これまでchat-uiはMac側から`kubectl port-forward svc/chat-ui 3000:80`で到達させていた
（[0004-chat-ui-tech-stack](0004-chat-ui-tech-stack.md)）。mock-api・MCP Serverは
既にKong DP + `minikube tunnel`経由（`http://localhost/mock-api`、
`http://localhost/mcp/world-monthly-temperature`）で統一的に外部公開されているため
（[0001-mock-api-service-exposure](0001-mock-api-service-exposure.md)、
`docs/design-brief.md`検証ログ）、chat-uiだけport-forwardに頼っている非対称を解消し、
port-forwardを常駐させなくてもアクセスできるようにしたい、という利用者からの指摘を受けた。

## 検討した選択肢

1. **ホストベースルーティング（例: `nip.io`）**: `chat-ui.127.0.0.1.nip.io`のような
   専用ホスト名で`KongRoute`を作り、パス変換（`strip_path`）を一切行わない。
   Next.js側の設定変更が不要で、mock-apiの`KongRoute`定義とも独立している。
2. **パスベースルーティング（`/chat-ui`）+ Next.js `basePath`設定**: mock-apiと
   統一感のあるURL構造（`http://localhost/chat-ui`）になるが、Next.jsアプリ自体に
   `basePath: '/chat-ui'`を設定し、`KongRoute`側は`strip_path: false`にする必要がある
   （`strip_path: true`にすると、アプリが生成する`/chat-ui/_next/...`等の絶対パスが
   Kongに届く前に失われ、静的アセットが404になる）。

## 決定

選択肢2（パスベース + `basePath`）を採用した（利用者の指示）。

## 判断基準・根拠

- mock-api・MCP Serverと同じ`http://localhost/<path>`という統一的なURL構造になり、
  デモ全体のアクセス手順（`INSTRUCTIONS.md`）がシンプルに保てる
- `nip.io`はhosts解決のみを外部DNSに依存する軽量な仕組みだが、実行環境によっては
  社内ネットワークでの外部DNS疎通が制限されている可能性があり、ローカルデモの
  再現性という観点ではパスベースの方が依存が少ない

## 想定していたこと vs 実際どうだったか

- 想定: `next.config.js`に`basePath: '/chat-ui'`を設定すれば、アプリ内の
  リクエスト・アセット参照は自動的にプレフィックス込みで解決される
- 実際: 2箇所で自動化されない箇所があった（詳細:
  [troubleshooting-log.md 2026-09-05](../troubleshooting-log.md)）。
  1. `@ai-sdk/react`の`useChat()`がデフォルトで叩く`/api/chat`は`next/link`と異なり
     自動プレフィックスされないため、`DefaultChatTransport`の`api`に
     `/chat-ui/api/chat`を明示する必要があった
  2. アプリのルートが`/chat-ui`になり`/`が404になるため、
     `deploy/chat-ui/chat-ui.yaml`のreadinessProbe/livenessProbe
     （コンテナポートに直接アクセス）のパスも`/chat-ui`に修正する必要があった
- 実機検証（2026-09-05）: `http://localhost/chat-ui`にブラウザでアクセスし、
  デモクエリ「過去10年の3月の平均気温Top5を教えてください」を送信して
  期待通りのTop5（Jakarta/Singapore/Khartoum/Luanda/Chennai）が返ることを確認

## 影響・トレードオフ

- `basePath`はビルド時にクライアントバンドルへ埋め込まれる値のため、変更する場合は
  イメージの再ビルドが必要（`next.config.js`と`app/page.tsx`の値を手動で同期させる
  運用上の負担が残る）
- port-forwardが不要になった一方、`minikube tunnel`の常駐が新たな前提条件になった
  （ただしmock-api・MCP Serverで既に同じ前提を要求しているため、実質的な追加負担はない）

## 関連する決定

- [0001-mock-api-service-exposure](0001-mock-api-service-exposure.md)
  （同じくKong DP + `minikube tunnel`経由の公開パターン）
- [0004-chat-ui-tech-stack](0004-chat-ui-tech-stack.md)（chat-ui技術スタック）
