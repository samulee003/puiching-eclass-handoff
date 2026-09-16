# 跨裝置同步設定（勾選＋積分）

`index.html`（家長）、`abigail.html`（李悅）、`gloria.html`（李昕）預設只用瀏覽器
`localStorage`。要讓三台裝置隨時看到同一個進度，接上 Firebase Realtime Database
即可；未設定時照常本機使用，不會壞。

同步內容只有兩種，不含 eClass 密碼：

- 勾選：`puiching-eclass-todos-v1`
- 積分：`puiching-eclass-points-v1`（含已得、已換、兌換紀錄）

功課本身（`status.json`）照舊由 Grok 掃 eClass 後推 `main` 更新，不走這條同步。

## 1. 建立 Firebase 專案（一次）

1. 在 Firebase Console 建立一個專用專案。
2. 建立 **Realtime Database**，位置按家庭需要選擇。
3. 在 **Authentication → Sign-in method** 開啟 **Anonymous**。
4. 將 `firebase.rules.json` 的內容貼到 Realtime Database Rules 並發布。
5. 在 Project settings 新增 Web app，複製 Web SDK config。
6. 把 config 填入 `sync-config.js` 的空白欄位。這些 Web config 值可出現在
   網頁，但 **不要** 把 service-account JSON、私鑰、密碼、OTP 或 cookie 放進 repo。
7. Commit/push 後等待 GitHub Pages 發布。

Firebase Web API key 不是資料庫授權；真正的保護來自 Anonymous Auth、Realtime
Database Rules，以及只有家人持有的高熵同步碼。不要把同步碼放到公開 README、
issue 或聊天群組。

## 2. 配對裝置

1. 在家長頁打開最下方的「☁️ 雲端同步」，按「產生同步碼」。
2. 按「複製同步碼」，用私人方式交給小孩平板。
3. 在 `abigail.html` / `gloria.html` 最下方打開「☁️ 雲端同步」，貼上同一組碼按「連接雲端」。
4. 三邊都看到「已同步 ☁️」後，任一邊勾選或賺積分，其他裝置幾秒內跟上。

同步碼只存在各裝置的 `localStorage`；忘記時在其中一台產生新碼，其他裝置重連即可。

## 3. 安全與 fallback

- 同步碼為 20 個隨機英數字元，雲端路徑只儲存同步碼的 SHA-256 雜湊。
- Firebase 只接受已登入的匿名裝置，且每筆寫入必須帶有目前裝置的 auth UID。
- 網路中斷、Firebase 未設定或 CDN 無法載入時，頁面仍使用本機 `localStorage`，重連後自動補送。
- 不要把 eClass 密碼、OTP、session cookie 或任何家長登入資料放進同步資料。
- 按「停止同步」會清除本機同步碼，但保留本機勾選與積分。
