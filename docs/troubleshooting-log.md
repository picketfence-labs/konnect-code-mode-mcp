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

## 2026-09-04 デモと無関係なファイルの混入（current.yaml, kong-ns.json）
- **何を期待していたか**: 作業ディレクトリのuntrackedファイルは、本デモに関連するもののみ
- **実際どうだったか**: `current.yaml`（Kafka関連の別プロジェクトのdecK設定と推測）、
  `kong-ns.json`（Kubernetes namespace削除処理のデバッグダンプ）という、本デモと無関係な
  ファイルが2件残っていた
- **原因**: 不明（別プロジェクトの作業や`kubectl`デバッグ操作の出力リダイレクトがこの
  ディレクトリに誤って残ったものと推測）
- **対処・回避方法**: 削除（コミット`b5ca6bf`に含む前にrm）
- **コスト**: 軽微
