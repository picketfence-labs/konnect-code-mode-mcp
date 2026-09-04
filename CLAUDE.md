# CLAUDE.md

このリポジトリで作業する Claude / コーディングエージェント向けのプロジェクト指針。

**基本設計（現在＋将来の要件・アーキテクチャ・優先順位）は [docs/design-brief.md](docs/design-brief.md) を参照。
本ファイルより詳細な背景・判断根拠はそちらが上位情報源。**

## プロジェクト概要

Kong Konnect の **Context Mesh**（<https://github.com/kong-gateway/context-mesh>）を使い、
**AI エージェントの LLM トークン量削減**を実証するサンプル/デモを構築する。

- 核心機能: **Code Mode**（FastMCP の `CodeMode` transform）。API から取得した大量データを
  サンドボックス内 Python で加工し、**加工後の小さな結果だけ**を AI エージェントに返す。
- 詳細な調査結果・実装方針は [CODE_MODE.md](CODE_MODE.md) を参照（本ファイルの上位情報源）。

## デモの目的（受け入れ条件）

API が約 1 万件のレコードを返す状況で、AI エージェントからのリクエストに応じて以下を実行し、
**結果のみ**を返せることを示す:

1. レコードのグループ化
2. グループごとの特定フィールド値の集計（Sum / 平均）
3. 算出値の Top5 のみを AI エージェントに返す

さらに、MCP エンドポイントが tool リクエストとしてデータ加工要件も受け付け、Code Mode で
データ処理を含む MCP サーバーを生成する、という一連の流れを見せる。

### 具体的なテストケース / データ

- テストデータ: **世界主要 100 都市 × 12 か月 × 10 年 (2016–2025) = 12,000 レコード**
  （[mock-api/](mock-api/)、実データが無いため決定論的に生成した近似値、`temp` は摂氏 °C）。
- **正規化**された 2 エンティティ:
  - `cities`: `id, city, country, latitude, longitude`（100 件）
  - `temperatures`: `id, city_id (FK→cities.id), year, month, temp`（12,000 件）
- API エンドポイント:
  - `GET /cities`（listCities）: 全都市の **id と都市名のみ**
  - `GET /cities/{city_id}`（getCity）: 1 都市の詳細
  - `GET /temperatures?city_id=`（getTemperatures）: 指定都市の気温（**city_id 必須**）
- 想定クエリ: **「過去 10 年の 3 月の平均気温 Top5 を取得」**。正規化のため、サンドボックス内で
  `listCities` → 各 `getTemperatures(city_id)` をループ集計する（**約 100 回のツール呼び出し**）。
- このデータ/モック API は**ローカル単体検証と Konnect 実証テストの両方で上流 API として再利用**する。
- 検証手順: [CODE_MODE_LOCAL_TEST.md](CODE_MODE_LOCAL_TEST.md)。

## デプロイ構成

- **定義（コントロールプレーン）**: Konnect UI 上で行う。
- **実行（データプレーン）**: ローカル Kubernetes（**Minikube、準備済み**）上に Kong DP と
  Context Mesh コンポーネント（Kong Operator / MCP Server Pod 等）をデプロイ。

## ドキュメント規約

- **ダイアグラムは必ず Mermaid 形式で記述する**（ASCII アートは使わない）。アーキテクチャ図・
  シーケンス図・データフロー図などはすべて ` ```mermaid ` コードブロックで書くこと。

## 役割分担 / 進め方

- **Konnect UI 上の作業は Shinichi（ユーザー）が確認しながら進める。** エージェントは
  Konnect UI を直接操作しない。UI 側で必要な操作は手順として提示し、確認を仰ぐこと。
- ローカル（Minikube / OpenAPI spec / 生成コード / サンプル API）側はエージェントが実装可。
- 外部サービスへの公開・不可逆操作は事前確認する。

## 技術スタック / 主要コンポーネント

- **oas-to-python** (Go): OpenAPI 3.0 → FastMCP(Python) 生成器。`--code-mode` で Code Mode 化。
- **FastMCP** 生成サーバーのランタイム。ローカル検証は最新 `fastmcp[code-mode]==3.4.2`
  + `requests==2.34.2`（`oas-to-python` の `runtime-requirements.txt` 自体は `3.3.1` ピン留め）。
- **init-container** (shell): CP の `/code` から生成 Python を取得。
- **mcp-server-runner**: 共有ボリューム上の `app.py` を起動。
- **Kong Operator**: `--feature-gates=mcp-server` で MCPServer CRD を扱う。
- **Kong Gateway** (hybrid mode) + **Konnect Control Plane**。

## 主要な制約 / 注意点

- **ローカル検証は FastMCP 最新版 `3.4.2` 前提**（`max_tool_calls` は v3.4.0 導入）。
  ⚠️ ただし `oas-to-python` の `runtime-requirements.txt` は `fastmcp==3.3.1` をピン留め
  （3.3.1 には `max_tool_calls` が無く、渡すと `TypeError`）。使う版で挙動が変わる点に注意。
- **`max_tool_calls`（3.4.x 既定 50）**: 正規化 API のため想定クエリは ~100 回呼ぶ → 既定 50 超過。
  生成 `app.py` の `CodeMode(...)` に `max_tool_calls=200`（または `None`）を追加（CLI フラグは無い）。
- **サンドボックス時間**: `MontySandboxProvider` の既定は `max_duration_secs=10` / `max_memory=50MB`
  （oas-to-python 生成コード）。メモリは 12,000 件 ≈ 1.1MB で収まるが、100 回の HTTP が実行時間に
  含まれるため時間超過に注意。超えたら生成 `app.py` の `MontySandboxProvider(limits=...)` を引き上げる。
- 生成ツールは list レスポンスを `{"results": [...]}` で包む（加工コードで参照するキー）。
- egress ガードにより、サンドボックス内コードは設定した upstream origin 以外へ通信不可。
- 認証は接続ヘッダー（`X-Upstream-Api-Key`/`X-Upstream-Bearer-Token`）推奨＝モデルに秘匿情報を見せない。
- Claude Code は array/object の MCP ツール引数を JSON 文字列化することがある既知不具合あり
  （`context-mesh/oas-to-python/docs/ProductDemo.md`）。引数は極力単純に。
- `mcp-translator` は On Hold。今回は使わない。

## リポジトリ構成（本リポジトリ）

| パス | 内容 |
|---|---|
| `README.md` | リポジトリの趣旨・構成・全体像 |
| `INSTRUCTIONS.md` | デモ検証手順（デプロイ後の疎通・クエリ・Top5 / トークン削減の確認） |
| `deploy/README.md` | Minikube デプロイ手順（mock-api） |
| `CODE_MODE.md` | Context Mesh / Code Mode 調査メモ・アーキテクチャ・実装方針 |
| `CODE_MODE_LOCAL_TEST.md` | デモ設計 + ローカル単体検証手順（通常は実施不要） |
| `mock-api/` | デモ用モック API（気温）+ テストデータ + OpenAPI spec |
| `mock-api/generate_data.py` | テストデータ生成器（決定論的、cities/temperatures を出力） |
| `mock-api/data/cities.json` | 生成済み 100 都市 |
| `mock-api/data/temperatures.json` | 生成済み 12,000 気温レコード |
| `mock-api/server.py` | FastAPI モック API（`/cities`, `/cities/{id}`, `/temperatures`） |
| `mock-api/openapi.json` | OpenAPI 3.0.3 spec（`oas-to-python` 用 / Konnect 登録用） |
| `mock-api/Dockerfile` | mock-api コンテナイメージ定義 |
| `deploy/mock-api/` | mock-api の K8s マニフェスト（Namespace/Deployment/Service ClusterIP） |

今後追加予定: Kong DP / Kong Operator マニフェスト、生成 FastMCP サーバー。

## 未確定事項（要確認）

- Konnect UI で Code Mode を有効化する手段の有無（UI トグル or spec 指定）。→ Shinichi 確認。
- 現テナントで MCP Composer / Context Mesh が利用可能か（Technical Preview 段階）。→ Shinichi 確認。
- Minikube 上の Kong Operator への `mcp-server` feature gate 投入手順。
- **（最優先、2026-09-04追加）Kong Operator の image tag アップグレード検証**: 現在の実運用手順
  （社内SE手順書、`~/LOCAL_REPO/context-mesh`起点。本リポジトリには未取り込み）は
  `docker.io/kong/nightly-kong-operator:20260623` に固定しているが、これは当時「デプロイしても
  Konnect 側で MCP Server の状態確認が取れない」という Operator 側バグの回避策。新しいタグで
  再検証し、解消していれば置き換える。詳細: [docs/design-brief.md](docs/design-brief.md) 2章
- **（2026-09-04追加）実運用手順の本リポジトリへの一本化**: 現時点でKong Operatorインストール・
  Konnect UI操作の実運用は `~/LOCAL_REPO/context-mesh`（upstream `kong-gateway/context-mesh` の
  reference clone、**変更禁止**）を起点に行っている。以後は本リポジトリだけで再現できるよう、
  手順を `deploy/kong-operator/` 等に取り込む（詳細: [docs/design-brief.md](docs/design-brief.md)）

## 参照

- 調査メモ: [CODE_MODE.md](CODE_MODE.md)
- 上流リポジトリ: <https://github.com/kong-gateway/context-mesh>
- FastMCP Code Mode: <https://gofastmcp.com/servers/transforms/code-mode>
