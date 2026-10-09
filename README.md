# あばらや話題帳

GitHub Pagesで公開する、あばらや204号室Rとバイヤー高橋の非公式アーカイブです。

- 6秒ライブ／ジャズフェス／公開収録などの話題からPodcast回を探す
- 話題の見出しや回の題名に一致する回を先に表示し、会話中に単語が出ただけの回は折りたたんで下へ
- YouTube動画は関連候補があるものを初期表示し、「候補なし」「すべて」へ切り替え
- LISTENの時間から公式Podcast音声を再生
- 公式配信ページ・LISTEN文字起こし・YouTubeにリンク

`archive.json` は公開されている公式RSS、LISTENのページ、YouTube公開情報から作ったスナップショットです。全文音声・全文文字起こしはこのリポジトリに含めません。動画の候補は共通する語句を使った検索結果で、動画について実際に話した確定記録ではありません。

## GitHub Pages

`main` にpushすると `.github/workflows/pages.yml` がPagesへ公開します。GitHubのリポジトリ設定「Pages」でBuild and deploymentのSourceを「GitHub Actions」に設定してください。
