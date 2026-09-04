# Troubleshooting Log

想定通りに動かなかったこと・想定と実際のギャップを、判断ポイントかどうかに関わらず漏れなく記録する。
1件＝1エントリ、追記専用。（[Troubleshooting Log Template](https://github.com/picketfence-labs/obsidian-vault/blob/main/06-Templates/Troubleshooting%20Log%20Template.md)、Obsidian Vault管理）

## 2026-09-04 Kong Operatorのimage tag固定（バグ回避策、未解消）
- **何を期待していたか**: Kong Operatorをインストールし、`DataPlane`をKonnectに接続すれば、
  Konnect UI上でMCP Serverのデプロイ状態（healthy等）が確認できる
- **実際どうだったか**: 特定バージョンのKong Operatorでは、デプロイ自体は成功してもKonnect側で
  MCP Serverの状態確認が取れない不具合があった
- **原因**: Kong Operator側のバグ（詳細不明。社内SE手順書作成時点で既知の問題として、
  回避策のみ共有されていた）
- **対処・回避方法**: `docker.io/kong/nightly-kong-operator:20260623`にimage tagを固定して
  デプロイすることで回避。**未解決**: より新しいタグで問題が解消しているかは次回検証する
  （`docs/design-brief.md`2章「現在の要件」1番目、最優先事項）
- **コスト**: 不明（社内SEチームでの発見経緯は本リポジトリでは追跡していない）

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
