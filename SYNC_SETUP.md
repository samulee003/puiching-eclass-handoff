# 跨裝置同步設定

`index.html`（家長筆電）和 `kids.html`（小孩平板）原本只用瀏覽器
`localStorage`。要跨裝置同步，這個專案提供可選的 Firebase Realtime Database
連接；未設定時仍會照常使用本機模式。

## 1. 建立 Firebase 專案

1. 在 Firebase Console 建立一個專用專案。
2. 建立 **Realtime Database**，位置按家庭需要選擇。
3. 在 **Authentication → Sign-in method** 開啟 **Anonymous**。
4. 將 `firebase.rules.json` 的內容貼到 Realtime Database Rules 並發布。
5. 在 Project settings 新增 Web app，複製 Web SDK config。
6. 把 config 填入 `sync-config.js` 的空白欄位。這些 Web config 值可出現在
   網頁，但 **不要** 把 service-account JSON、私鑰、密碼、OTP 或 cookie 放進 repo。
7. Commit/push `sync-config.js` 後等待 GitHub Pages 發布。

Firebase Web API key 不是資料庫授權；真正的保護來自 Anonymous Auth、Realtime
Database Rules，以及只有家人持有的高熵同步碼。不要把同步碼放到公開 README、
issue 或聊天群組。

## 2. 配對筆電與平板

1. 在家長筆電打開 `index.html`，按「產生同步碼」。
2. 按「複製同步碼」，把同步碼用私人方式交給家人。
3. 在小孩平板打開 `kids.html`，輸入同一組同步碼並按「連接雲端」。
4. 兩邊看到「已同步 ☁️」後，完成勾選或「進行中」狀態會同步。
5. 平板可用 `kids.html?child=li-yue` 或 `kids.html?child=li-xin` 直接進入指定小孩。

同步碼只存在各裝置的 `localStorage`，雲端儲存的是完成／看板狀態，不會回寫
`status.json` 或 `DASHBOARD.md`。忘記同步碼時，必須在其中一台產生新碼，
再在另一台重新連接；舊房間資料不會自動搬到新碼。

## 3. 安全與 fallback

- 同步碼為 20 個隨機英數字元，雲端路徑只儲存同步碼的 SHA-256 雜湊。
- Firebase 只接受已登入的匿名裝置，且每筆狀態必須帶有目前裝置的 auth UID。
- 網路中斷、Firebase 未設定或 CDN 無法載入時，頁面仍使用本機 `localStorage`。
- 不要把 eClass 密碼、OTP、session cookie 或任何家長登入資料放進同步資料。
- 若要停止同步，按「停止同步」；這會清除本機保存的同步碼，但保留本機任務勾選。
