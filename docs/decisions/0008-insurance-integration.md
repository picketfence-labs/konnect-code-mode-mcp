# 0008. Insurance API と Context Mesh の統合方式

- **日付**: 2026-09-28
- **状態**: Accepted

## コンテキスト

検索ツールを複数 API に広げ、保険商品・顧客・申込・契約・請求の参照と保険料試算を一つの
MCP Server から扱えるようにする。Insurance API の6サービスは Kubernetes の `insurance`
namespace ですでに稼働している（イメージ `v0.1.1`）。既存の Kong Control Plane / Data Plane
を使い、Gateway の構成を二重化せずに Context Mesh へ接続したい。

## 検討した選択肢

1. **A: bundle のデプロイスクリプトを実行する**。必要なサービスはデプロイできるが、
   `insurance-cp` と Gateway も作成する。既存の Control Plane / Data Plane と重複するため却下。
2. **B: `demo` namespace に別名でコピーする**。既存の `insurance` サービスと同じ API が
   二重に稼働し、状態や更新の管理も分かれるため却下。
3. **B': bundle manifest の固定コピーを `insurance` namespace に置く**。既存サービスを
   同じ名前・ラベル・ポートで再現し、イメージを `v0.1.1` に固定する。新しい KongService / 
   KongRoute は追加せず、MCP Server からサービス DNS で直接接続する。これを採用する。
4. **C: bundle repository の manifest を毎回直接適用する**。動作はするが、隣接 checkout の
   有無や状態に再現性が依存するため却下。

## 決定

選択肢 B' を採用する。`deploy/insurance/services.yaml` は bundle の
`k8s/services/services.yaml` を基にした固定コピーとし、タグだけを `v0.1.1` に固定する。
既存の Kubernetes Service 名と DNS（`<svc>.insurance.svc.cluster.local:8000`）を利用する。

Context Mesh には6つの Source を登録し、一つの MCP Server `kong-insurance` から公開する。
Source ごとの操作は、product / customer / application / policy / claim が各2件、simulation
が1件の合計11件とする。CRUD API は読み取り操作だけを残し、simulation はステートレスな
試算 POST のみを残す。デモに必要な検索と試算を示しつつ、顧客・契約データを書き換えない範囲に
絞るためである。

bundle の OpenAPI 3.1.0 を Context Mesh 用の 3.0.3 に変換する。null union は `nullable: true`
へ、schema `examples` は `example` へ、`const` は単一値 `enum` へ変換し、3.0.3 と無関係な
schema marker を除く。変換ルールと操作許可リストは `scripts/build_insurance_specs.py` に置き、
bundle の更新は内容を確認した明示的な PR でスクリプトを再実行して取り込む。

将来は Issue #20 で、一つの Chat UI から World Weather と Insurance の両 MCP Server に接続する。

## 判断基準・根拠

- すでに稼働しているサービスをそのまま使うことで、不要な Pod や Gateway を作らずに済む。
- 固定コピーとタグ固定により、fresh clone でも同じマニフェストを適用でき、現在のクラスタへ
  適用した場合も同一のオブジェクトになる。
- OpenAPI をソースから再生成できるため、手編集による source と登録用仕様のずれを抑えられる。

## 影響・トレードオフ

- Insurance サービスの更新は自動追従しない。bundle の変更を確認し、manifest と仕様を更新する
  PR が必要となる。
- 顧客データは架空だが、マイナンバーに似た値を含む。デモ回答では個別の顧客行を表示しない。
- Konnect UI への Source / MCP Server 登録は手動で行い、登録後の URL とツール一覧を記録する。

## 関連資料

- [Insurance デプロイ・Konnect 登録手順](../../deploy/insurance/README.md)
- Issue [#19](https://github.com/picketfence-labs/konnect-code-mode-mcp/issues/19)
- Issue [#20](https://github.com/picketfence-labs/konnect-code-mode-mcp/issues/20)
