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
各 Source には **bundle の OpenAPI 仕様（v0.1.2、OpenAPI 3.1.0）を無変更で**登録する。
「手元の OpenAPI 仕様をそのまま登録するだけで MCP Server 化できる」ことが、このデモで示したい
価値だからである。v0.1.1 までの仕様は `servers` が例示用のドメイン（`https://api.example.com/<svc>`）
だったため、bundle 側で `http://<svc>.insurance.svc.cluster.local:8000` に改めた
（kong-api-bundle-insurance PR #19、v0.1.2）。本 repo には仕様のコピーを置かず、bundle の v0.1.2
タグを参照する。Pod のイメージは `v0.1.1` のままとする（v0.1.2 との差分のうち `services/` 配下は
`openapi.yaml` だけで、API の動作は同じ）。

操作は絞り込まず、書き込み系（POST / PUT / DELETE）と `/health` も含めた32操作を公開する。
書き込み系は Chat UI の指示で使わせないようにし、データが書き換わった場合は Pod を再起動して
seed に戻す（各サービスはデータをプロセス内のメモリに保持している）。

将来は Issue #20 で、一つの Chat UI から World Weather と Insurance の両 MCP Server に接続する。

## 判断基準・根拠

- すでに稼働しているサービスをそのまま使うことで、不要な Pod や Gateway を作らずに済む。
- 固定コピーとタグ固定により、fresh clone でも同じマニフェストを適用でき、現在のクラスタへ
  適用した場合も同一のオブジェクトになる。
- OpenAPI 仕様を変えずに登録するので、元の仕様と登録内容がずれない。登録した仕様の `servers` は
  MCP Server が使う上流 URL の既定値になる（runner のコードに埋め込まれる）。Context Mesh は
  OpenAPI 3.1.0 をそのまま受け付ける（2026-09-28、bundle の仕様で32操作が Tool 化されることを確認）。
- 当初は「3.0.3 へ変換し、読み取りと試算の11操作に絞る」案を採った（World Weather の仕様が
  3.0.3 だったことからの推測）。しかし 3.1.0 が受け付けられることを確認し、デモの価値を優先して
  「`servers` だけ置き換えて登録する」案に改めた（同日）。さらに、`servers` の修正を bundle 側へ
  入れ、無変更で登録できるようにした（2026-09-29、v0.1.2）。

## 影響・トレードオフ

- Insurance サービスの更新は自動追従しない。bundle の変更を確認し、manifest と参照するタグを
  更新する PR が必要となる。
- 書き込み系の操作も LLM から呼べる。Chat UI の指示で抑止するが、保証ではない。データが
  書き換わった場合は `kubectl -n insurance rollout restart deploy` で seed に戻す。
- 公開する Tool が増える（32個）ため、Search Tool で必要な Tool を探す場面がより明確になる。
- 顧客データは架空だが、マイナンバーに似た値を含む。デモ回答では個別の顧客行を表示しない。
- Konnect UI への Source / MCP Server 登録は手動で行い、登録後の URL とツール一覧を記録する。

## 関連資料

- [Insurance デプロイ・Konnect 登録手順](../../deploy/insurance/README.md)
- Issue [#19](https://github.com/picketfence-labs/konnect-code-mode-mcp/issues/19)
- Issue [#20](https://github.com/picketfence-labs/konnect-code-mode-mcp/issues/20)
