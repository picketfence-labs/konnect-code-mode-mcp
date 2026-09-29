# Insuranceテストケースの実測証跡（Opusが2026-09-29に取得）

[TEST_INSURANCE.md](../../../TEST_INSURANCE.md)の根拠となる、2026-09-29に実クラスタで取得した証跡（ログの全文と英語の回答全文）。TEST_INSURANCE.mdのログ節は、ここから抜粋している。

## 環境
| 項目 | 値 |
|---|---|
| 実施日時 | 2026-09-29 15:47〜15:52 JST（06:47〜06:52 UTC） |
| Chat UI | `main` `a57553b`（PR #24の2 MCP Server同時接続を含む）を`next build`し、ローカルの`next start -p 3100`で起動。`MCP_WEATHER_URL=http://127.0.0.1/mcp/world-monthly-temperature`、`MCP_INSURANCE_URL=http://127.0.0.1/mcp/kong-insurance`（`minikube tunnel`経由）。クラスタ上のChat UI（`chat-ui:0.1.0`）ではない |
| LLM | `gemini-3.5-flash`（Chat UIの既定） |
| MCP Server | `kong-insurance`（Context Mesh MCP Server 3.3.1、runner `kong/mcp-server-runner:0.6.0`）。6 Source、32 Tool |
| 登録した仕様 | kong-api-bundle-insurance **v0.1.3**の`services/<svc>/openapi.yaml`を無変更で登録（英語のsummary／description）。Tool名は`property_dash_insurance_dash_<svc>_dash_api_<operationId>`（simulationは`property_dash_insurance_dash_premium_dash_simulation_dash_api_...`） |
| Insurance API | `insurance` namespace、image `v0.1.1`（seedの状態。書き込み操作は実行していない） |
| 日本語の質問 | ブラウザ（Playwright）から実行し、画面を保存 |
| 英語の質問 | Chat UIのAPI（`POST /chat-ui/api/chat`）へ直接送信。画面キャプチャは無い。回答全文は`I-*-en-answer.md` |

## 画面キャプチャ（`assets/images/`）
| ファイル | 内容 |
|---|---|
| `assets/images/chat-ui-insurance-i1-conversion-rate.png` | I-1（日本語）。Tool: Insurance list_tools → get_schema → execute ×2 |
| `assets/images/chat-ui-insurance-i2-paid-claims.png` | I-2（日本語、「ステータスが支払済」を明示した質問）。list_tools → get_schema → execute ×3 |
| `assets/images/chat-ui-insurance-i2-ambiguous-run.png` | I-2（日本語、設計どおりの質問）。**基準値と一致しなかった回**（下記） |
| `assets/images/chat-ui-insurance-i3-premium-simulation.png` | I-3（日本語）。**search** → get_schema → execute |

## ケースごとの結果

### I-1 申込から契約への成立率
- 日本語の質問: 「商品ごとに申込件数と成立した契約件数を集計し、成立率の高い順に上位5商品を示してください。申込と契約は別のAPIから取得してください。」
- 英語の質問: "For each insurance product, count applications and issued policies, then show the top five by policy conversion rate. Retrieve applications and policies from their respective APIs."
- Tool呼び出し（日・英とも）: `insurance_list_tools` → `insurance_get_schema` → `insurance_execute` ×2
- 回答（日・英とも基準値と完全一致）: 自動車保険「ドライブセーフ」54件／40件／74.07% → 傷害保険「ケガの安心サポート」59／41／69.49% → ペット保険「わんにゃんメディカル」68／46／67.65% → 火災保険「住まいの安心」71／45／63.38% → 医療保険「メディカルサポート」48／28／58.33%。成立率＝契約件数÷申込件数
- 上流API（`I-1-*-insurance-api.log`）: 1回目のexecuteでproduct／application／policyを少数件ずつ取得してデータの形を確認し、2回目でproduct 1回、application 3回（skip 0／100／200、limit 100）、policy 2回（skip 0／100）を呼んで全件を取得している（日・英とも同じパターン）
- 生成コード: `I-1-*-mcp-server.log`（1回目のexecuteでデータの形を確認し、2回目で集計）

### I-2 支払済請求額
- **設計どおりの質問**（日本語）: 「支払済みの保険金請求額を商品別に合計し、上位5商品を示してください。請求対象の契約から商品を特定してください。」
  - 結果: **基準値と一致しなかった**。回答は火災39,563,922円、傷害11,654,702円、自動車5,872,134円、医療1,250,942円、ペット886,584円（36件）
  - 原因（`I-2-ja-ambiguous-mcp-server.log`）: 生成コードが`claim_amount_paid`が0より大きい請求を集計した。ステータス「承認」の請求にも`claim_amount_paid`が入っているため、「支払済＋承認」の合計になった（2026-09-29の別の試行でも、この値が参考値として出ていた）
  - 教訓: 業務上の条件（どのステータスを「支払済」とみなすか）は、質問で明示しないとLLMの解釈で結果が変わる
- **条件を明示した質問**（テストケースとして採用）
  - 日本語: 「ステータスが「支払済」の保険金請求だけを対象に、支払額を商品別に合計し、上位5商品を示してください。請求対象の契約から商品を特定してください。」
  - 英語: "Consider only insurance claims whose status is 支払済 (paid). Sum the paid amounts by insurance product and show the top five. Resolve each claim's product through its policy."（statusの値は日本語のままなので、質問に日本語の値を含める）
  - Tool呼び出し: 日本語 `insurance_list_tools` → `insurance_get_schema` → `insurance_execute` ×3、英語 `insurance_list_tools` → `insurance_get_schema` → `insurance_execute` ×2
  - 回答（日・英とも基準値と完全一致）: 火災23,497,720円 → 傷害9,884,887円 → 自動車4,662,288円 → 医療1,250,942円 → ペット639,214円（支払済28件）
  - 英語の質問でも、回答は日本語だった（statusの値に日本語を含めたためとみられる）
  - 生成コードは`status == '支払済'`で絞り込み、`claim_amount_paid`がnullの場合は0として扱っている（`I-2-ja-mcp-server.log`）

### I-3 保険料の試算（Searchで試算Toolを選ぶ）
- 日本語の質問: 「既存契約の保険料ではなく、新規の自動車保険PRD-002を1990-01-01生・補償額300万円で試算し、月額と年額を教えてください。」
- 英語の質問: "Quote a new PRD-002 auto policy for a person born on 1990-01-01 with ¥3,000,000 coverage. Report the monthly and annual premium. Do not report premiums from existing policies."
- Tool呼び出し: **日本語では`insurance_search` → `insurance_get_schema` → `insurance_execute`**。英語では`insurance_list_tools` → `insurance_get_schema` → `insurance_execute`（同じ質問でも、searchを使うかどうかはLLMの判断で変わる）。searchに渡したqueryは記録していない
- 回答（日・英とも）: 年齢36歳、月額4,580円、年額55,000円
- 独立の確認: Opusが同じ引数（`product_id: PRD-002`、`birth_date: 1990-01-01`、`sum_insured: 3000000`）でMCPの`execute`から試算Toolを直接呼び、同じ値（monthly_premium 4580、annual_premium 55000、age 36、base_annual 55000）を得た
- 上流API: simulationへ`POST /simulations`が1回だけ。**データを変更しない**試算で、policyの作成（`POST /policies`）は呼ばれていない
- 注意: 試算は実行日の年齢で計算するため、日付が変わると金額が変わり得る（固定の期待値にしない。2026-09-29時点の実測値として書く）

## searchについての実測（同日、MCPへ直接）
| query | 件数 | 上位 |
|---|---:|---|
| `申込一覧の取得` | 0 | —（日本語は0件） |
| `list applications` | 9 | list_applications が1位 |
| `premium quote` | 7 | 試算（simulate）が1位 |
| `underwriting` | 2 | descriptionにだけある単語でヒット |
| `insurance products` | 32 | 全件（Source名の`insurance`が全Toolに含まれる） |

## execute内のimport（同日、両方のMCP Serverで同じ結果）
- 成功: `asyncio`、`json`、`math`、`re`、`datetime`
- 失敗（`ModuleNotFoundError`）: `collections`、`statistics`

## World Weatherの回帰確認（同日）
- 「過去10年の3月の平均気温Top5を教えてください」を2回実行し、どちらも`weather_*`のToolだけを使って、Jakarta 29.09 → Singapore 28.13 → Khartoum 27.90 → Luanda 27.49 → Chennai 27.34（℃）を返した（既存TESTのテストケース1と一致）。画面キャプチャとログは取っていない

## ログについての注意
- `*-mcp-server.log`は`kubectl logs --timestamps`でrunnerから取得した。**runnerは生成コードと`Result:`を1リクエスト遅れて書き出す**ため、タイムスタンプは次のリクエストが届いた時刻になる。Opusはexecuteの実行順（`chat-ui-chat_completed.log`の`toolCalls`）に従って、ブロックをケースへ割り当てた
- `*-insurance-api.log`はInsuranceの各Podのuvicornのアクセスログ（`/health`を除く）で、時刻はそのまま
- 顧客の個人情報（氏名、マイナンバーに似た値）はログにも回答にも含まれていない（Opusが確認）
