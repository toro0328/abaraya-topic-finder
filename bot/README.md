# 毎日あばらや X bot

毎日、日本時間の20時ごろに2件投稿します。

- その月日と同じ日に配信された回があれば、その中から1本を紹介
- 該当回がなければ「今日は該当回なし」と表示し、代わりのランダム回を1本紹介
- もう1件は全アーカイブ（R・旧回）から選ぶランダム回
- 同じ日に出す2件は別の回。旧回には「旧」、R回には「R」を付ける
- 旧回の投稿日が未登録でも、ランダム選出には含める

選択結果は日付をもとに決まるので、同じ日のプレビューは毎回同じです。投稿はX API v2の投稿エンドポイントを使います。

## 旧回の文字起こし

旧回の音声からWhisperのタイムスタンプ付き下書きを作る手順は [`transcription-README.md`](transcription-README.md) を参照してください。

## 初期設定

1. X Developer Portalでアプリを作成し、ユーザー認証をOAuth 1.0aに設定して、投稿権限を有効にします。
2. GitHubのリポジトリ設定から **Settings → Secrets and variables → Actions** を開き、次の4つをRepository secretsとして登録します。
   - `X_API_KEY`
   - `X_API_SECRET`
   - `X_ACCESS_TOKEN`
   - `X_ACCESS_TOKEN_SECRET`
3. `.github/workflows/daily-x-bot.yml` を既定ブランチに取り込むと、毎朝の自動投稿が有効になります。
4. まずActionsから手動実行し、`dry_run=true` のプレビューを確認します。実投稿する手動実行では `dry_run=false` を選びます。

APIキーやトークンはコードに書かず、GitHub Secretsだけに保存してください。X APIの利用料金・利用条件は変わることがあるため、Developer Portalで有効化前に確認してください。

## ローカル確認

```sh
python -m pip install -r bot/requirements.txt
python -m unittest discover -s bot -p 'test_*.py'
DRY_RUN=true python bot/daily_post.py
```


## 既存アカウントの投稿を空にする

同じXアカウントのOAuth 1.0a認証情報をRepository secretsに登録したあと、GitHubの **Actions → Clean up X account posts → Run workflow** を開きます。

1. 初回は `dry_run=true` のまま実行し、対象アカウント名と投稿件数を確認します。投稿は消えません。
2. 対象が合っていて、表示件数が想定どおり（例：191件）なら、もう一度実行して `dry_run=false`、`expected_count` にその件数を入力します。
3. 投稿IDごとに削除します。件数が一致しなければ処理を止めます。APIのレート制限時はリセットまで待ってから続行します。

削除は取り消せません。X APIで対象になるのは、認証したアカウント自身の投稿です。認証情報をチャットに貼らず、GitHub Secretsにだけ登録してください。
