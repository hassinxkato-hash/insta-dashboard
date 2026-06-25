# 店舗インスタ投稿ダッシュボード（クラウド自動版）

GitHub Actions が毎朝クラウドで投稿状況を取得し、ダッシュボードを Web 公開します。
**PC不要・全員はURLを開くだけ**。設定は最初の一度だけです。

## 仕組み

```
GitHub Actions（毎朝7時・自動） → fetch.py が146店舗を取得
   → docs/index.html を再生成 → GitHub Pages が自動でWeb公開
   → 社員は公開URLを開くだけ（最新表示・ログイン不要）
```

## 含まれるファイル

| ファイル | 役割 |
|---|---|
| `fetch.py` | 取得＆ダッシュボード生成（トークンは環境変数から読む） |
| `accounts.csv` | 対象146アカウント一覧 |
| `.github/workflows/update.yml` | 毎日自動実行の設定 |
| `docs/index.html` | 公開されるダッシュボード（自動で上書き） |

---

## STEP 1. GitHub リポジトリを作る

1. https://github.com/ でアカウント作成（無料）
2. 右上「＋」→「New repository」
3. 名前を入力（例：`insta-dashboard`）。**Private 推奨**（※下の注意参照）
4. 「Create repository」
5. このフォルダ（`github_repo` の中身）を**そのままアップロード**
   - 「uploading an existing file」リンク → ドラッグ＆ドロップ
   - `fetch.py` / `accounts.csv` / `.github` / `docs` が入っていることを確認

## STEP 2. トークンを Secrets に登録（秘密の保管庫）

リポジトリの **Settings → Secrets and variables → Actions →「New repository secret」** で登録：

| Name | Value |
|---|---|
| `IG_ACCESS_TOKEN` | 取得した長期アクセストークン（必須） |
| `IG_APP_ID` | アプリID（任意・トークン延長用） |
| `IG_APP_SECRET` | app secret（任意・同上） |
| `IG_USER_ID` | 空でOK（自動取得。指定したい場合のみ） |

> トークンはここ（暗号化される場所）にだけ入れます。ファイルやコードには絶対に書きません。

## STEP 3. GitHub Pages を有効化（Web公開）

1. **Settings → Pages**
2. 「Build and deployment」の Source を **「Deploy from a branch」**
3. Branch を **`main`** / フォルダを **`/docs`** に設定して保存
4. 数十秒後、公開URL（例：`https://ユーザー名.github.io/insta-dashboard/`）が表示される
   → これが**全員に配るURL**です

## STEP 4. 初回実行

1. **Actions タブ**を開く（初回は「I understand my workflows, go ahead and enable them」を承認）
2. 左で「**Update Instagram Dashboard**」を選択
3. 右上「**Run workflow**」→「Run workflow」で手動実行
4. 緑のチェックが付いたら成功。公開URLを開くと最新ダッシュボードが表示されます

以降は**毎朝7時（JST）に自動更新**されます。手動で今すぐ更新したいときは STEP 4 の Run workflow を押すだけ。

---

## 運用メモ

- **対象は公開のプロアカウントのみ**。非公開・個人アカウントは空欄になるので、
  `accounts.csv` の該当行を手で埋めてください（`エリア`列も入れると絞り込み可）。
- **店舗の追加・削除**は `accounts.csv` を編集してコミットするだけ。
- **トークンの有効期限は60日**。期限が近づいたら新しい長期トークンを発行し、
  STEP 2 の `IG_ACCESS_TOKEN` を更新してください（`IG_APP_ID`/`IG_APP_SECRET` を
  入れておくと毎回延長を試みますが、確実なのは手動更新です）。
- **更新時刻の変更**は `.github/workflows/update.yml` の `cron` を編集（UTC基準）。

## 注意：公開範囲について

- **Private リポジトリ**なら、Secrets もコードも非公開です。ただし無料プランの
  GitHub Pages は Public 扱いになる場合があるため、ダッシュボードURLを知っている人は
  閲覧できます（中身は元々公開Instagram情報の集約なので機微度は低めです）。
- 完全に社内限定にしたい場合は、社内サーバーやアクセス制限付きホスティングへの
  配置に切り替えられます（必要なら相談してください）。
