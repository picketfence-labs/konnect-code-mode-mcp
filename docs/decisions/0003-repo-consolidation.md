# 0003. 実運用手順の一本化先（本リポジトリ vs context-meshクローン）

- **日付**: 2026-09-04
- **状態**: 決定

## コンテキスト
2026-09-04時点で、Kong Operatorのインストール・Konnect UIでのMCP Server定義といった
実運用手順は、本リポジトリ（`konnect-code-mode-mcp`）ではなく`~/LOCAL_REPO/context-mesh`
（upstream `kong-gateway/context-mesh`のreference clone。Obsidian Vault
`07-Sources/repos/kong-gateway-context-mesh`に「変更禁止・参照専用」として登録済み）を
起点に、社内SE手順書（`Kong Operator Context Mesh - SE's.md`）に従って行われていた。
本リポジトリにはmock-apiのソース・OpenAPI spec・Minikubeデプロイマニフェスト・調査ドキュメント
のみがあり、実際にKong Operatorをインストールする手順は含まれていなかった。

## 検討した選択肢
1. **現状の分離を維持**: `~/LOCAL_REPO/context-mesh`を実運用の起点にし続け、
   `konnect-code-mode-mcp`はmock-apiソース+ドキュメント置き場という役割分担のまま
2. **`konnect-code-mode-mcp`に一本化**: 社内SE手順書のKong Operatorインストール手順
   （Helm/CRD定義）を本リポジトリに取り込み、以後は本リポジトリだけで再現できるようにする

## 決定
選択肢2（本リポジトリへの一本化）を採用した。

## 判断基準・根拠
- `~/LOCAL_REPO/context-mesh`はupstream repoのreference clone（変更禁止の参照専用として
  Obsidian Vaultに登録済み）であり、実運用の作業ディレクトリとして使い続けると、
  upstreamの更新（`git pull`等）時に作業成果が混在・消失するリスクがある
- 本リポジトリ（`konnect-code-mode-mcp`）は「社内向けの継続的なリファレンスデモ」
  （`docs/design-brief.md`1章、将来要件）として今後も保守する対象であり、再現手順が
  1リポジトリに閉じている方がハーネス整備（Dev Repo Bootstrap Checklist準拠）とも相性が良い
- `~/LOCAL_REPO/context-mesh`自体は今後も**参照専用**（コード生成器・ランタイムの一次情報源
  としての読み取り）として引き続き有用なため、削除・移動はしない

## 想定していたこと vs 実際どうだったか
- 想定: 社内SE手順書のHelm/CRD定義をそのまま`deploy/kong-operator/`に移植すれば済む
- 実際: 手順書の値（Kong Gateway `3.14`、DataPlane replicas `3`）と、実際に稼働している
  クラスタの値（`3.15`、replicas `1`）が異なっていた。再現性を優先し、**実機で確認済みの値**
  （`3.15`、replicas `1`）を採用した。また手順書のimage tag（`20260623`）は
  [ADR-0005](0005-kong-operator-image-tag-upgrade.md)で`20260904`へ更新済みのため、
  そちらの決定を継承した
- KPATをファイルに残さないよう、`KonnectAPIAuthConfiguration`はテンプレート化
  （`konnect-resources.yaml.template`、`${KPAT}`を`envsubst`で展開する運用）にした
- 「新規cloneからのゼロ構築」の実機再現（`docs/design-brief.md`5章の検証基準）は、既存の
  Konnect Control Plane/DataPlaneを壊すコストが高いため今回は見送った（未実施）

## 影響・トレードオフ
- 移植作業自体に一定のコストがかかる（社内SE手順書のHelm/CRD定義をリポジトリ内のマニフェストに
  変換し、image tag等の環境依存値を本リポジトリの`deploy/`規約に合わせる）
- 一本化後は、Kong Operator自体の更新（新しいCRD・feature-gate等）を追随する責務も
  本リポジトリ側に移る

## 関連する決定
- [0001-mock-api-service-exposure](0001-mock-api-service-exposure.md)
- [0002-demo-api-choice](0002-demo-api-choice.md)
