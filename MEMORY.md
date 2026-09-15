# MEMORY.md — 培正 eClass 功課看板現況快照

更新日期：2026-09-15（Asia/Macau）。改行為或改資料的 agent 必須同步更新本檔日期與受影響段落。

## 一句話現況

清爽版 UI＋勾選／積分雲端同步已接線，但 Firebase Web config 還是空的；工作區有未提交改動，PR #4 仍是草稿，合併前不要假設公開站已更新。

## 分支與發布

- 工作分支：`cursor/setup-dev-environment-29da`
- 工作區狀態：10 個已修改＋4 個未追蹤（見下表）；未 commit
- PR #4：草稿，未合併
- 發布規則：經 PR 合併到 `main` 才會上 GitHub Pages；合併需要使用者明確同意

## 真相來源（以這兩個為準）

- `status.json`：機器真相，`updated_at` 為 `2026-09-15T11:10:00Z`
- `DASHBOARD.md`：人類／備援真相，最後更新為 2026-09-15（劉備覆寫李悅區塊）

### 今日功課摘要

| 孩子 | 今日 | 近期 | 閉環 |
|---|---|---|---|
| 李悅 Abigail P3 | 中文第3課習作、數學習作6 p.14、英文 Wb. p.14、Wb. p.16（共 4） | 9/16 兩項、9/20 拼字、9/22 背書、9/17 Quiz、10/16 口試、勤讀獎 0/20 | 待回 |
| 李昕 Gloria P1 | 無今日項 | 9/16 聽力測驗、9/23 工作紙＋默字、9/25 認讀、其他 3 | 待回 |

獎勵：每項 10 分，當日全清再加 20 分；軟糖 50、巧克力 80、洋芋片 120、雪糕 150。

## 頁面與資料流

- `index.html`：家長總覽，先顯示兩孩待辦，日曆／時程摺疊
- `abigail.html`／`gloria.html`：小孩平板頁；不直接信任 JSON 的 `due_today`／`due_soon` 標籤，一律按澳門今天重算顯示
- 勾選鍵：`puiching-eclass-todos-v1`；積分鍵：`puiching-eclass-points-v1`
- 同步鍵：`puiching-eclass-sync-code-v1`；離線待送：`puiching-eclass-sync-pending-v1`
- 同步只寫勾選＋積分，不回寫 `status.json`／`DASHBOARD.md`

## 雲端同步狀態

- 已實作：`sync.js`、`sync-config.js`（空佔位）、`firebase.rules.json`、`SYNC_SETUP.md`，三頁皆已接線
- 未完成：Firebase Web config 七個值全空；未連線測試；未 commit
- 下一步：使用者貼回 `apiKey`、`authDomain`、`databaseURL`、`projectId`、`storageBucket`、`messagingSenderId`、`appId` → 填入 `sync-config.js` → 驗證 → commit → 三裝置用同一組同步碼配對

## 待確認

1. 今日兩孩閉環皆「待回」
2. PR #4 草稿合併時機（需使用者點頭）
3. `DASHBOARD.md` 9/15 已拿掉李昕存密備註，但 `AGENTS.md` 仍留著 9/14 的 Password Manager 舊注記；動登入前先跟家長確認
4. `status.json` 的 `rewards` 區塊被移到檔尾，屬排版差異，驗證器只看結構不看順序

## 決策與紅線

- 版面保持乾淨：次要資訊摺疊，不搶待辦
- 積分採每孩 last-write-wins：正常每孩只有自己的平板會寫分
- 禁止進 repo：密碼、OTP、session cookie、私鑰；同步碼也不公開
- 對使用者一律繁體中文，先講下一步

## 接手順序

1. `MEMORY.md`
2. `AGENTS.md`
3. `status.json`（優先）＋ `DASHBOARD.md`
4. `SOP.md`
5. 改完跑 `python3 scripts/validate_status.py`
