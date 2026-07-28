# Consulting Week Session Feedback

Consulting Week（2026-07-28、Asia/Tokyo）専用の匿名イベント回答フォームです。
既存IFM・顧客向けアンケートとは、画面ルート、設定、データcollectionを分離しています。

## URL

- 回答: `https://ifmsurveybuilder-dm4twazgypcxpcagcebod5.streamlit.app/?event=consulting-week-2026`
- 管理: `https://ifmsurveybuilder-dm4twazgypcxpcagcebod5.streamlit.app/?event=consulting-week-2026&view=admin`
- ローカル回答: `http://localhost:8501/?event=consulting-week-2026`
- ローカル管理: `http://localhost:8501/?event=consulting-week-2026&view=admin`

## 起動

```powershell
uv run --with-requirements requirements.txt streamlit run autodesk_assessment.py
```

管理画面は既存の `sales_admin.password` を再利用します。秘密値をソースコードへ
追加しないでください。

## データ

- Firestore collection: `event_responses_consulting_week_2026`
- document id: `{respondent_id_hash}_{session_id}`
- 一意性: `(event_id, respondent_id_hash, session_id)`
- 生のブラウザUUID: ブラウザのlocalStorageだけに保持
- サーバー保存ID: サーバー秘密値からイベント固有に導出したHMAC-SHA256
- 1回の同期: dirtyなセッションのみ、最大16件
- 同期時のDB read: dirtyなセッションの既存文書だけ
- 同期時のDB write: 内容が変わった文書だけ

既存の `responses`、`surveys`、Google Sheets「成熟度回答」へは読み書きしません。

## 回答UX

- Submitボタンなし
- 操作直後にlocalStorageへ保存
- 1秒debounce、サーバー同期は最低5秒間隔
- 同期中は画面上部のフローティング通知を表示し、回答操作を妨げない
- 同期完了時に通知を消す
- 回答済みカードを折り畳み、次の未回答カードを開く
- 3部タブと各部末尾の切替ボタンを用意
- オフライン時は回答を端末に残し、オンライン復帰時に再送

## 管理とCSV

管理画面はアジェンダ順に以下を表示します。

- expectation / actual の平均と回答数
- paired回答だけを使った total / gap の平均
- skipped数
- retrospective expectation数
- 最終更新時刻

CSVはセッション別集計と匿名回答の2種類です。匿名回答CSVに生UUIDや完全な
respondent hashは含めません。

## QRコード

管理画面からPNGをダウンロードできます。ローカル配布用の同一QRは
`output/consulting-week-2026-response-qr.png` に生成します。

## イベント終了後

1. 必要な2種類のCSVを管理画面から保存する。
2. `data/consulting_week_2026.json` の `status` を `closed` に変更してデプロイする。
   回答画面は受付終了表示になり、管理画面とデータは残る。
3. 保持期間の終了後、Firestoreの
   `event_responses_consulting_week_2026` collection内の文書だけを削除する。
4. 完全撤去時は `autodesk_assessment.py` のイベントルートとConsulting Week専用
   ファイルを削除する。既存IFM collectionは削除しない。

## デプロイ

本番Streamlit Community CloudはGitHub `main` を参照しています。テスト後に
変更をcommitし、`origin/main`へpushすると再デプロイされます。反映後は回答URL、
管理URL、QR、スマートフォン表示、Firestore Upsertを本番で再確認してください。
