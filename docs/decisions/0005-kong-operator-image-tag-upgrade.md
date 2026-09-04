# 0005. Kong Operatorのimage tagアップグレード（バグ回避策の解消）

- **日付**: 2026-09-04
- **状態**: 決定・実施済み

## コンテキスト
社内SE手順書に基づき、Kong Operatorは`docker.io/kong/nightly-kong-operator:20260623`に
image tagを固定してデプロイしていた（Helm chart `kong-operator-1.3.0`）。これは当時
「デプロイ自体は成功してもKonnect側でMCP Serverの状態確認が取れない」というKong Operator側の
バグの回避策だった（詳細: [troubleshooting-log.md](../troubleshooting-log.md)）。
`docs/design-brief.md`2章の最優先事項として、より新しいタグでこの問題が解消しているかを
検証する必要があった。

## 調査
`~/LOCAL_REPO/kong-operator`（読み取り専用の参照clone）でCHANGELOG.mdおよびgit historyを
調査した結果:
- 稼働中Podのログから、固定タグ`20260623`の実体commitは`fb9ede2af`（2026-06-20）と判明
- このcommitは、PR [#4795](https://github.com/Kong/kong-operator/pull/4795)
  （"EventGateway / MCPServer: fix Server-Side Apply (SSA) permanently failing with
  'no corresponding type'... permanently breaking SSA — including status writes —
  until the next restart"、2026-07-07マージ、`v2.3.0-rc.1`〈2026-07-15リリース〉収録）より
  **前**であることを`git merge-base --is-ancestor`で確認。つまり固定タグ自体が、報告された
  症状（Konnect側でのステータス確認不可）に一致する既知バグを含んでいた可能性が高い
- 一方、2026-08-11（PR [#5134](https://github.com/Kong/kong-operator/pull/5134)）に
  `MCPServer`/`MCPServerDataPlane`のCRD分割という、本検証とは無関係な破壊的変更が
  main branchに入っている

## 検討した選択肢
1. **`20260810`（SSA修正を含み、CRD分割より前）**: 今回の検証対象（SSA修正）に限定した
   最小リスクの選択。当初の推奨案
2. **最新の`20260904`**: 「最新に近いものを選定する」（`design-brief.md`5章）という方針に
   最も忠実。CRD分割後のため、Helm chartも`kong-operator-1.3.0`のままでは新CRD
   （`mcpserverdataplanes.mcp.konghq.com`）が導入されず、chartのアップグレードも合わせて
   必要になる

## 決定
選択肢2（`20260904`）を採用し、Helm chartも`kong-operator-1.3.0`→`1.4.0`
（appVersion `2.3.0`）へ合わせてアップグレードした。

```
helm upgrade kong-operator kong/kong-operator \
  --version 1.4.0 \
  -n kong-system \
  --set image.repository=docker.io/kong/nightly-kong-operator \
  --set-string image.tag=20260904 \
  --set env.FEATURE_GATES=mcp-server \
  --set env.ENABLE_CONTROLLER_KONNECT=true
```

## 判断基準・根拠
- 利用者の判断（最新に近いものを優先。CRD分割の影響は許容）
- Helm chartの`crds/`特殊ディレクトリではなく通常テンプレート（`charts/ko-crds/templates/`）で
  CRDが管理されているため、chartを`1.4.0`にアップグレードすれば`helm upgrade`で新CRDも
  正しく反映されることを事前に確認済み（Helmの「`crds/`はinstall時のみ適用され、upgradeでは
  新規CRDが追加されない」という既知の制約に該当しない構成だった）
- 既存の`MCPServer`（`test-30f18e2a`、Konnect名`world-monthly-temperature`、Mirror方式）は
  CRD分割後も後方互換で動作し続けることを実機で確認（旧`MCPServer`単体で`PROGRAMMED: True`を
  維持、`MCPServerDataPlane`への強制移行は不要だった）

## 想定していたこと vs 実際どうだったか
- 想定: 新タグへの切り替え自体は単純作業で、検証の焦点はKonnect UI上のstatus表示のみ
- 実際: `helm upgrade --set image.tag=20260904`がHelmの数値型自動変換により
  `docker.io/kong/nightly-kong-operator:%!s(int64=20260904)`という壊れたイメージ参照を生成し、
  複数回アップグレードが失敗した（詳細:
  [troubleshooting-log.md](../troubleshooting-log.md)「Helm `--set` の数値型誤変換」）。
  `--set-string`への変更で解消。この既知のHelmの落とし穴は、日付形式（`YYYYMMDD`）や
  純数字のバージョン文字列をタグに使うKong Operatorのnightly運用と特に相性が悪いため、
  今後`deploy/kong-operator/`に手順を取り込む際は必ず`--set-string`を使うことを明記する
- 検証結果: アップグレード前後ともKonnect UI上の「world-monthly-temperature」MCP Serverの
  statusは"Healthy"（利用者が実機確認）。アップグレード前から既にHealthyだった点は、
  本セッション冒頭でクラッシュしていたOperator Podを別件（minikube再起動直後の一時的な
  API server接続タイムアウト）で再起動した際に、SSAの型コンバータが再構築され症状が
  一時的に解消していた可能性がある（CHANGELOGの記述「until the next restart」と整合）。
  そのため今回の検証は「新タグでも回帰なく動作する」ことの確認が主眼となった

## 影響・トレードオフ
- Helm chartを`1.3.0`→`1.4.0`に上げたことで、`MCPServerDataPlane` CRDや
  `EventGatewaySchemaRegistry` CRD等、本デモで使わない機能のCRDも追加された
  （実害なし、CRD自体は宣言のみ）
- 今後`docs/design-brief.md`2章の要件2（リポジトリの一本化）で`deploy/kong-operator/`に
  手順を移植する際は、image tagをchart 1.4.0 + `20260904`（または以後の後継タグ）を
  起点にする

## 関連する決定
- [0003-repo-consolidation](0003-repo-consolidation.md)
