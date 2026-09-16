# Original User Request

## 2026-09-15T13:01:53Z

為培正 eClass 雙孩功課看板（puiching-eclass-handoff）打造全自動「懶人整合方案」（B+C 方案）：
1. 自動化 Firebase 雲端同步打通：基於 Firebase CLI 自動化配置 Realtime Database、產生並填入 Web SDK config 至 sync-config.js、部署安全規則，並在 index.html 提供一鍵產出 QR Code / 配對連結，讓兩孩平板免手動輸入代碼即可一鍵連線。
2. 自動化 eClass 家課表抓取與更新工作流：實作自動化抓取與解析工具，能登入 eClass 家課表、自動依規則過濾（李悅略過所有進階科、李昕無進階）、雙寫更新 status.json 與 DASHBOARD.md，並通過 validate_status.py 驗證。

Working directory: /Users/samulee003/Downloads/puiching-eclass/puiching-eclass-handoff
Integrity mode: development

## Requirements

### R1. Firebase 自動化打通與極簡配對
- 透過 Firebase CLI 腳本化流程建立/關聯 Firebase 專案、啟用 Realtime Database 與匿名認證，自動提取 Web SDK 金鑰寫入 sync-config.js，並發布 firebase.rules.json。
- 在家長總覽頁（index.html）提供「一鍵產生 QR Code / 快速配對 URL」，讓小孩平板（abigail.html / gloria.html）掃描或點擊後自動載入家庭同步碼，實現零打字即時同步。
- 嚴格遵守無密碼與安全隔離紅線，未連線或未配置時無縫自動降級為本機模式。

### R2. eClass 家課表自動化抓取與結構化解析
- 提供可運行的 eClass 抓取與解析腳本（支援無頭瀏覽器或安全 HTTP 會話），接受環境變數傳入帳密（禁止寫死在代碼或 git）。
- 登入培正 eClass 後，依序抓取李悅（Abigail）與李昕（Gloria）之家課表。
- 嚴格遵守業務過濾規則：
  - 李悅（P3）：略過所有科目名稱含「進階」的項目，口試/Quiz 須抓取完整詳情內文。
  - 李昕（P1）：無進階分流，確保抓取學生身分正確。
  - 共同：不論是否「須繳交」（如不用繳交但需在家完成者）皆需列入，並依截止日正確歸類（今日必做、近期、測驗、其他）。

### R3. 看板雙寫真相與合規驗證
- 抓取完成後，自動更新 status.json 與 DASHBOARD.md 兩份真相來源中各自孩子的區塊，保持兩者數據完全一致。
- 執行 scripts/validate_status.py 驗證更新後的 JSON 結構、合法日期與時間戳。

## Acceptance Criteria

### 1. Firebase 雲端同步與配對驗收
- [ ] 執行設定腳本後，sync-config.js 完整具備可用之 Web config，且資料庫規則部署成功。
- [ ] 家長頁可生成帶有同步參數的 QR Code 或連結；平板頁透過該 URL 開啟後自動完成配對並進入「已同步 ☁️」狀態。
- [ ] 模擬兩端連線下，待辦勾選與積分增減在 3 秒內雙向同步完成；斷網重連能自動補發離線佇列。

### 2. eClass 自動化抓取驗收
- [ ] 抓取工具能正確解析測試 HTML 樣本（fixtures）或即時頁面，產出包含科目、標題、截止日、是否需繳交與詳情之資料。
- [ ] 李悅之輸出資料中 100% 排除「進階」相關科目。
- [ ] 更新後的 status.json 執行 python3 scripts/validate_status.py 驗證通過（exit code 0），無欄位遺失或格式錯誤。

### 3. 安全性與穩健性
- [ ] 任何執行日誌、程式碼與 Git commit 中無明文密碼、Session Cookie 或私人金鑰。
- [ ] 當 eClass 登入失敗或 session 過期時，拋出明確的 LOGIN_REQUIRED 錯誤訊息，不偽造假數據。
