# Troubleshooting Log

想定通りに動かなかったこと・想定と実際のギャップを、判断ポイントかどうかに関わらず漏れなく記録する。
1件＝1エントリ、追記専用。（[Troubleshooting Log Template](https://github.com/picketfence-labs/obsidian-vault/blob/main/06-Templates/Troubleshooting%20Log%20Template.md)、Obsidian Vault管理）

## 2026-09-04 Kong Operatorのimage tag固定（バグ回避策）→ 検証・解消
- **何を期待していたか**: Kong Operatorをインストールし、`DataPlane`をKonnectに接続すれば、
  Konnect UI上でMCP Serverのデプロイ状態（healthy等）が確認できる
- **実際どうだったか**: 特定バージョンのKong Operatorでは、デプロイ自体は成功してもKonnect側で
  MCP Serverの状態確認が取れない不具合があった
- **原因**: Kong Operator側のバグ（詳細不明。社内SE手順書作成時点で既知の問題として、
  回避策のみ共有されていた）
- **対処・回避方法（当時）**: `docker.io/kong/nightly-kong-operator:20260623`にimage tagを
  固定してデプロイすることで回避
- **解消（2026-09-04検証）**: `~/LOCAL_REPO/kong-operator`のローカルclone調査により、当時の
  固定タグのcommit（`fb9ede2af`, 2026-06-20）は、PR
  [#4795](https://github.com/Kong/kong-operator/pull/4795)（"EventGateway / MCPServer: fix
  Server-Side Apply (SSA) permanently failing... including status writes"、2026-07-07マージ、
  `v2.3.0-rc.1`収録）より**前**のコミットであることが判明。つまり固定タグ自体が症状の原因に
  一致するバグを含んでいた可能性が高い。もっとも、稼働中のOperator Podを再起動すると
  （SSAの型コンバータがプロセス起動時に再構築されるため）症状が一時的に解消する経緯が
  changelogに明記されており、本セッションでの検証開始時（前段のPod再起動）でも実際に
  アップグレード前の時点でKonnect UI上は既に"Healthy"と表示されていた（ベースライン確認）。
  そのうえで、SSA修正を含み・かつ2026-08-11のMCPServer/MCPServerDataPlane CRD分割
  （無関係な破壊的変更）より前を狙う予定だったが、利用者の判断で最新nightly
  `docker.io/kong/nightly-kong-operator:20260904`（+ Helm chart `kong-operator`を`1.3.0`→
  `1.4.0`）へアップグレード。アップグレード後もKonnect UI上のstatusは"Healthy"のまま、
  既存の`MCPServer`（`test-30f18e2a`、Konnect名`world-monthly-temperature`）もCRD分割後の
  新チャートで`PROGRAMMED: True`を維持し、回帰無し。**結論: 解消（新タグへの置き換えを決定。
  詳細: [ADR-0005](decisions/0005-kong-operator-image-tag-upgrade.md)）**
- **コスト**: 調査・検証で約1時間（ローカルgit clone調査＋実機アップグレード＋Konnect UI確認）

## 2026-09-04 Helm `--set` の数値型誤変換によるimage tag破損（本件の調査中に発生）
- **何を期待していたか**: `helm upgrade --set image.tag=20260904 ...`で、Kong Operatorの
  imageタグが`docker.io/kong/nightly-kong-operator:20260904`になる
- **実際どうだったか**: 生成されたイメージ参照が
  `docker.io/kong/nightly-kong-operator:%!s(int64=20260904)`という壊れた文字列になり、
  Podが`InvalidImageName`でCrashLoopした。さらに`--wait`がPodの起動待ちを続けた結果、
  一見無関係な`Error: UPGRADE FAILED: client rate limiter Wait returned an error: context
  deadline exceeded`というエラーで複数回（revision 2〜5）失敗し、CRD数やAPI serverの
  レート制限が原因であるかのように見えた（実際はPodが永久に起動しないため`--wait`の
  ポーリングがタイムアウトしていただけ）
- **原因**: Helmの`--set`は値が数値に見える文字列（`"20260904"`等）を自動的にint64として
  解釈する既知の仕様。シェル側でクオートしても`--set`の値解析には影響しない
- **対処・回避方法**: `--set-string image.tag=20260904`を使うことで解決。数値に見えるタグ・
  バージョン文字列をHelmの`--set`で渡す際は常に`--set-string`を使うべき
- **コスト**: 誤ったエラーメッセージに引かれて原因調査に約15分

## 2026-09-04 mock-api/openapi.jsonのローカル検証URLとdescriptionの不整合
- **何を期待していたか**: `mock-api/openapi.json`の`servers[1]`（ローカル検証用エントリ）の
  URLとdescriptionが一致していること
- **実際どうだったか**: URLは`http://localhost/mock-api`（Kong DP経由を想定した値）に
  変更されていたが、descriptionは旧方式（`kubectl port-forward svc/mock-api 8088:80`）の
  説明文のままだった
- **原因**: `minikube tunnel`経由のKong DP到達方式へ切り替える途中の変更で、URLのみ更新し
  descriptionの更新が漏れたと推測（未commit差分の状態で発覚）
- **対処・回避方法**: descriptionを新方式（`minikube tunnel`経由、KongRoute `/mock-api`）の
  説明に修正。合わせて`deploy/README.md`に該当手順を追記した（コミット`b5ca6bf`）
- **コスト**: 精査に要した時間のみ。実害（誤ったURLでの検証実施等）は無かった

## 2026-09-04 .claude/settings.jsonへの壊れた許可エントリの混入
- **何を期待していたか**: `.claude/settings.json`の`permissions.allow`エントリが、いずれも
  有効な`Bash(<pattern>)`構文であること
- **実際どうだったか**: `"Bash(git commit -q -m ' *)"`という、引用符が浮いた不正な構文の
  エントリが混入していた
- **原因**: `git commit -q -m '...'`実行時に、コミットメッセージ中の引用符の扱いにより
  誤ったパターンとして自動記録されたと推測（未確認）
- **対処・回避方法**: 該当エントリを削除（コミット`b5ca6bf`）
- **コスト**: 軽微

## 2026-09-04 社内SE手順書とKonnect UI経由で実際に稼働している値の不一致（DataPlane）
- **何を期待していたか**: 社内SE手順書（`Kong Operator Context Mesh - SE's.md`）の
  `DataPlane`定義（`kong/kong-gateway:3.14`、`replicas: 3`）をそのまま
  `deploy/kong-operator/`へ移植すれば、現在稼働中の構成と一致する
- **実際どうだったか**: `kubectl get dataplane dataplane -o yaml`で確認した実際の稼働値は
  `kong/kong-gateway:3.15`、`replicas: 1`だった。手順書作成後にKonnect UI側の操作
  （MCP Server作成時のControl Plane再設定等）で変更された可能性があるが、いつ・誰が
  変えたかは追跡できなかった
- **原因**: 不明（手順書とUI操作履歴の間に記録されないドリフトがあった）
- **対処・回避方法**: 再現性を優先し、`deploy/kong-operator/`のマニフェストは手順書の値ではなく
  **実機で確認した稼働中の値**を採用した。今後手順書側の値と食い違う変更をUIから行った場合、
  本リポジトリのマニフェストへ書き戻すのを忘れないこと
- **コスト**: 軽微（`kubectl get -o yaml`での確認のみ）

## 2026-09-04 デモと無関係なファイルの混入（current.yaml, kong-ns.json）
- **何を期待していたか**: 作業ディレクトリのuntrackedファイルは、本デモに関連するもののみ
- **実際どうだったか**: `current.yaml`（Kafka関連の別プロジェクトのdecK設定と推測）、
  `kong-ns.json`（Kubernetes namespace削除処理のデバッグダンプ）という、本デモと無関係な
  ファイルが2件残っていた
- **原因**: 不明（別プロジェクトの作業や`kubectl`デバッグ操作の出力リダイレクトがこの
  ディレクトリに誤って残ったものと推測）
- **対処・回避方法**: 削除（コミット`b5ca6bf`に含む前にrm）
- **コスト**: 軽微

## 2026-09-04 `minikube tunnel`がエージェントの非対話シェルから起動不可（sudo要求）
- **何を期待していたか**: `minikube tunnel`をバックグラウンドで起動し、mock-apiのKong DP経由
  到達性を自動検証できる
- **実際どうだったか**: `dataplane-ingress-dataplane-*`（LoadBalancer）が80/443番ポートを
  要求するため、`minikube tunnel`は起動時に対話的な`sudo`パスワード入力を要求する。
  非対話バックグラウンドシェルからは入力できずプロセスが無限に待機状態になった
  （パスワードなしsudoも不可）
- **原因**: LoadBalancer Serviceが特権ポート（80/443）を使う構成のため、`minikube tunnel`が
  内部で`sudo`を呼ぶ仕様
- **対処・回避方法**: 待機中のプロセスをkillし、利用者本人にターミナルで直接
  `minikube tunnel`を実行してもらい、常駐させた状態で疎通確認（`curl`）を行った。
  起動後は`curl http://localhost/mock-api/health`等がKong経由（`X-Kong-Upstream-Latency`
  ヘッダーで確認）で200を返すことを確認済み
- **コスト**: 軽微（利用者への依頼1往復のみ）

## 2026-09-04 `deploy/README.md`のKong DP Service検索コマンドのラベルセレクタが実在しない
- **何を期待していたか**: `kubectl get svc -n default -l gateway-operator.konghq.com/dataplane-name
  -o wide`でKong DPのLoadBalancer Service（`dataplane-ingress-dataplane-*`）が見つかる
- **実際どうだったか**: `No resources found`。Chat UI用にMCP_SERVER_URLへ埋める内部Service名を
  確認しようとして気づいた
- **原因**: 実際にServiceへ付与されているラベルは`gateway-operator.konghq.com/dataplane-name`
  ではなく`app=dataplane`と`gateway-operator.konghq.com/dataplane-service-type=ingress`
  （`kubectl get svc ... -o jsonpath='{.metadata.labels}'`で確認）。以前このコマンドを
  ドキュメント化した際に未検証のまま記載したと推測
- **対処・回避方法**: `deploy/README.md`内の2箇所（mock-apiのKong DP到達確認手順・Chat UIの
  MCP_SERVER_URL確認手順）を`-l app=dataplane,gateway-operator.konghq.com/dataplane-service-type=ingress`
  に修正
- **コスト**: 軽微（`kubectl get svc -o wide`で全件確認して気づいた）

## 2026-09-04 MCP Server実体（app.py）はこのリポジトリから変更できない（ログ基盤設計の前提修正）
- **何を期待していたか**: ログ基盤（要件6）で「AI/MCP評価特化型」を実現するにあたり、
  MCP Server側にもtool呼び出し回数・レスポンスペイロードサイズを構造化ログとして
  出力する計装を追加できる想定だった
- **実際どうだったか**: MCP Serverの実体（`app.py`）はKonnect Control Planeが
  `oas-to-python`で生成し、Podの`init-container`が起動時に`/code`エンドポイントから
  取得する構成（[CODE_MODE.md](../CODE_MODE.md)参照）。**このリポジトリのコードとして
  存在せず、デプロイのたびにControl Planeから再取得される**ため、計装のための改修を
  このリポジトリ側から加える手段が無いと判明
- **原因**: ログ基盤の設計検討を始めた時点で、MCP Server側のコード管理主体
  （Control Plane生成 vs リポジトリ管理）を再確認していなかった
- **対処・回避方法**: 計装は自分たちで書いているコード（chat-uiの`onEnd`）に限定し、
  MCP Server側は追加計装なしで既存の非構造化ログ（Code Mode生成コード・`call_tool`結果を
  含む、実機確認済みで情報量は十分）をそのままLokiに収集する方針に転換。詳細:
  [ADR-0006](decisions/0006-log-observability-stack.md)
- **コスト**: 軽微（アーキテクチャドキュメントの再確認のみ。実装前の判明のため手戻りは無し）

## 2026-09-05 Next.js `basePath`設定で見落としやすい2箇所（chat-uiのKong route化）
- **何を期待していたか**: chat-uiをKong DP経由（`/chat-ui`パスプレフィックス）で公開する際、
  `next.config.js`に`basePath: '/chat-ui'`を設定すれば、アプリ内の全リクエスト・
  アセット参照が自動的にプレフィックス込みで解決されると想定していた
- **実際どうだったか**: 2箇所で想定外の挙動があった。
  1. `@ai-sdk/react`の`useChat()`がデフォルトで叩く`/api/chat`は、`next/link`と違い
     `basePath`が自動付与されない（クライアント側の素の`fetch()`呼び出しのため）。
     修正せずデプロイした場合、チャット送信がbasePath無しの`/api/chat`（404）を叩き失敗する
  2. `basePath`設定後、アプリのルートは`/`ではなく`/chat-ui`になる（`/`は404を返す）。
     そのため`deploy/chat-ui/chat-ui.yaml`の`readinessProbe`/`livenessProbe`
     （`path: /`、コンテナポート3000に直接アクセス）がKong経由か否かに関わらず
     常に失敗するようになる（`kubectl rollout status`がタイムアウトして気づいた）
- **原因**: Next.js公式ドキュメント（`basePath.md`）に、`next/link`によるリンクのみ
  自動プレフィックスされる旨は明記されているが、`fetch()`や外部からのヘルスチェック
  パスまでは対象外という点は事前に見落としていた
- **対処・回避方法**: (1) `useChat({ transport: new DefaultChatTransport({ api:
  '/chat-ui/api/chat' }) })`でAPIパスを明示。(2) readinessProbe/livenessProbeの
  `path`を`/chat-ui`に変更。いずれも`next.config.js`の`basePath`値と手動で
  同期させる必要がある点をコード中にコメントで明記した
- **コスト**: 軽微（`kubectl rollout status`のタイムアウトで(2)に気づくまで数分）

## 2026-09-05 Helmのネストしたsubchartで`.`を含む値キー（`grafana.ini`）を`--set`指定する際のエスケープ
- **何を期待していたか**: `grafana/loki-stack`（親chart）配下の`grafana`（`grafana/grafana`を
  aliasしたsubchart）に対し、Grafana自体のサブパス公開設定（`server.root_url`/
  `server.serve_from_sub_path`）を`--set grafana.grafana.ini.server.root_url=...`のような
  素直なドット区切りで`helm upgrade --set`指定できると想定していた
- **実際どうだったか**: 上記の書き方では値が正しく`grafana.ini`ConfigMapへ反映されなかった
  （`helm show values grafana/grafana`で確認すると、値キー自体が文字通り`grafana.ini`という
  ドットを含む1つのキー名になっており、単純なドット区切りのネストとは解釈が異なる）
- **原因**: Helmの`--set`はドットをネストの区切り文字として解釈するため、キー名自体に
  ドットを含む場合（`grafana.ini`）は区切り文字と衝突する
- **対処・回避方法**: `--set grafana."grafana\.ini".server.root_url=...`のように、ドットを
  含むキー部分をダブルクオート＋バックスラッシュエスケープで囲むことで正しく反映される。
  適用前に`helm upgrade --dry-run`でレンダリング結果の`ConfigMap`を確認して検証した
  （[deploy/observability/README.md](../deploy/observability/README.md)参照）
- **コスト**: 軽微（`helm show values`での構造確認と`--dry-run`検証で解決、約10分）

## 2026-09-05 macOS BSD `date -j -f`で末尾"Z"付き日時文字列がUTCではなくローカルタイムゾーンとして解釈される
- **何を期待していたか**: `date -j -f "%Y-%m-%dT%H:%M:%SZ" "2026-09-05T01:44:35Z" +%s`のように
  末尾に`Z`（UTC/Zuluを示す慣用表記）を含むフォーマット文字列を渡せば、UTCとしてパースされ
  正しいepoch秒が得られると想定していた
- **実際どうだったか**: macOS純正の`date`（BSD date）は`-f`のフォーマット文字列中の`Z`を
  単なるリテラル文字としてマッチさせるだけで、タイムゾーン指定としては扱わない。結果、
  ローカルタイムゾーン（JST, UTC+9）としてパースされ、算出したepoch秒が実際より9時間
  先の値になった。これによりLoki（`/loki/api/v1/query_range`）へのログ抽出クエリの
  `start`/`end`が実際のログ発生時刻の9時間先を指してしまい、該当ログが0件ヒットになった
- **原因**: GNU dateと異なり、BSD dateの`-f`はフォーマット文字列中の`Z`をタイムゾーン指定子
  として特別扱いしない。`-u`フラグを明示しない限り常にローカルタイムゾーンでパースされる
- **対処・回避方法**: `date -j -u -f "%Y-%m-%dT%H:%M:%SZ" ...`のように`-u`を明示することで
  UTCとして正しくパースされることを確認し、以降のログ抽出はすべて`-u`付きで実施した
- **コスト**: 中程度（Lokiクエリが0件を返す原因調査に約15〜20分）

## 2026-09-05 mcp-serverコンテナ標準出力のブロックバッファリングによる`Result:`ログの遅延フラッシュ
- **何を期待していたか**: TEST.md用にChat UIの各デモクエリを実行した直後、
  `kubectl logs deploy/mcpserver-test-<id>`で該当リクエストのCode Mode生成コードと、
  その実行結果（`Result: ...`）が両方とも確認できると想定していた
- **実際どうだったか**: あるリクエストの**ターン内最後の**`execute`呼び出しについては、
  クライアント（Chat UI）への応答が正常に返ってきているにもかかわらず、その`Result:`行が
  `kubectl logs`に一切現れないことが複数回発生した。ログを取得し直しても変化がなく、
  該当リクエストが完了して数分経っても現れなかったが、**次の別リクエストをmcp-serverに
  送信した直後**に、既に完了していたはずの前リクエストの`Result:`行が遅れて出現した
- **原因**: mcp-serverプロセスの標準出力がTTY非接続時のPythonデフォルトである
  ブロックバッファリングになっており、ターン内最後の`print()`はバッファが一定量埋まるか
  次の書き込みが発生するまでコンテナのログストリームにフラッシュされない
- **対処・回避方法**: 該当リクエストの直後に軽量なダミークエリ（例:「こんにちは」）を
  Chat UIへ送信し、mcp-serverへの追加書き込みを発生させることで、保留中のログを
  強制的にフラッシュさせて回収した。ログのタイムスタンプは実際の実行時刻ではなく
  フラッシュされたタイミングを示す点に注意が必要（mock-api側の実呼び出し時刻と
  突き合わせて実行時刻を特定した。詳細: [TEST.md](../TEST.md)「検証方法メモ」）
- **コスト**: 中程度（原因特定・回避策の確立に約20〜30分）

## 2026-09-05 Chat UIがブラウザリロードをまたいで会話コンテキストを保持しており、直前のテストの内容を誤って再利用することがある
- **何を期待していたか**: TEST.md用の各テストケースを、ブラウザで`http://localhost/chat-ui`へ
  都度navigateし直してから新しいクエリを送信すれば、Chat UIの表示上は新規会話に見える通り、
  サーバー側（LLMに渡る会話コンテキスト）も独立した1ターンとして扱われると想定していた
- **実際どうだったか**: 複数のテストケースで、新しいクエリを送った直後の**最初の**`execute`
  呼び出しが、直前に実行した**別のテストケース**の月・集計ロジックをそのまま（またはほぼ
  そのまま）再利用したコードを生成し、誤った回答候補を一瞬導出する挙動が繰り返し観測された
  （例: 8月クエリの1回目の`execute`が3月クエリのコード・結果をそのまま返す）。いずれも
  その後の`execute`で自己修正し、UIに表示される最終回答自体は正しかった
- **原因**: 未特定。ブラウザリロードによってフロントエンドの表示（メッセージ履歴）は
  リセットされるが、サーバー側でセッションCookie等により会話コンテキストが保持されて
  いる可能性がある（chat-uiの実装未調査。本セッションでは深追いせず）
- **対処・回避方法**: TEST.mdのログ抽出では、各テストケースの**入力内容と実際に整合する**
  コードブロックのみを実ログから選別して掲載し、無関係な再利用ブロックは除外した
  （詳細: [TEST.md](../TEST.md)「検証方法メモ」）。今後同様の検証を行う場合、真に独立した
  会話履歴で試したい場合はブラウザのシークレットウィンドウ等でCookieを分離することを推奨
- **コスト**: 中程度（複数テストケースで同様の挙動が再現し、正しいログの選別に都度時間を要した）

## 2026-09-05 並行して進んでいた2つのPRがINSTRUCTIONS.mdに独立して重複・矛盾するセクションを追加
- **何を期待していたか**: 本ブランチ（`docs/instructions-chat-ui-screenshot`）の作業中に
  `main`へ他のPRがマージされても、`git merge origin/main`で機械的にマージできると
  想定していた
- **実際どうだったか**: `main`側で先にマージされたPR #9（Chat UIスクリーンショット追加）が、
  本ブランチの最初のコミットと**同じ目的の変更**をINSTRUCTIONS.mdへ独立に追加していたが、
  挿入位置が異なっていた（本ブランチは既存の「§3」を直接拡張、PR #9は新規「§3.5」として
  追加）。さらにPR #10（chat-uiのKong route化）がマージされた後も、PR #9由来の「§3.5」は
  port-forward前提の旧手順のまま取り残されており、実装（PR #10）とドキュメント（§3.5）が
  矛盾した状態でmainに存在していた。本ブランチの§3（Kong route前提に更新済み）とマージした
  際、この重複箇所でコンフリクトが発生した
- **原因**: 同じINSTRUCTIONS.md更新作業が、本ブランチと（気づかないまま）別途mainへ直接／
  別ブランチ経由でマージされる形で並行して行われたため。作業開始前に`main`の最新状態や
  他の進行中PRの有無を確認していなかった
- **対処・回避方法**: マージ後、実装（Kong route）と矛盾するPR #9由来の「§3.5」を削除し、
  内容が最新かつ実装と整合する本ブランチの「§3」に一本化。`gh pr view --json mergeable`で
  `MERGEABLE`/`CLEAN`になったことを確認してからpushした
- **コスト**: 軽微（コンフリクト自体の解消は数分。ただし今後同種のドキュメント作業を
  始める前に`git fetch && git log main..origin/main`等で他の並行作業の有無を確認する
  ひと手間を怠らないこと）
