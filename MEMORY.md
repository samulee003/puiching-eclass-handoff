# MEMORY.md — 培正 eClass 功課看板現況快照

更新日期：2026-09-17（Asia/Macau）。改行為或改資料的 agent 必須同步更新本檔日期與受影響段落。

## 一句話現況

全自動雙孩 eClass 爬蟲工作流（GitHub Actions 定時同步）全面打通且實測成功！雙孩（李悅 P3、李昕 P1）各自憑證經 GitHub Secrets 登入，透過巢狀表格堆疊解析器成功自真實培正 eClass 抓取實時家課（共 23 項紀錄），依截止日期精準分類，完全不依賴任何 AI / Grok 額度，100% 免費運作！

## 核心里程碑完成狀況

1. **M1 雲端同步與免打字配對（已全線打通上線）**：
   - 透過 Firebase CLI / Management API 完成真實雲端環境配置：
     - 專案：`puiching-eclass`（Spark 方案 $0 永久免費）
     - 資料庫：`puiching-eclass-default-rtdb`（位於 `asia-southeast1` 新加坡）
     - 認證方式：已成功啟用匿名認證（Anonymous Authentication）
     - 安全性規則：已部署 `firebase.rules.json` 至雲端 RTDB
     - Web App：已建立 `puiching-web` 並將正式客戶端 Config 寫入 `sync-config.js`
     - 雲端實測：經由端對端腳本驗證匿名登入、資料庫安全規則、讀取與寫入，雙向即時同步 100% 成功。
   - `index.html` 內建原生 SVG QR Code 向量產出（`assets/qrcode.min.js`，零外部 API 依賴、無資安外洩風險）。
   - 兩孩平板頁面（`abigail.html` / `gloria.html`）支援讀取 `?familyId=`、`?sync=` 等參數實現零打字一鍵配對。

2. **M2 eClass 自動抓取引擎與 GitHub Actions 零額度排程（已全面實裝並通過實測）**：
   - 工作流檔案：`.github/workflows/eclass-sync.yml`。
   - 執行時程：平日（週一至週五）15:30 澳門時間（07:30 UTC）自動定時執行，並支援 `workflow_dispatch` 手動一鍵觸發。
   - 雙帳號隔離：使用者已於 GitHub Secrets 設定 4 個金鑰（`ECLASS_LI_YUE_USERNAME`, `ECLASS_LI_YUE_PASSWORD`, `ECLASS_LI_XIN_USERNAME`, `ECLASS_LI_XIN_PASSWORD`）。
   - 培正 eClass 協定實作：
     - 先向 `/templates/` 提取 CSRF `securetoken`。
     - 向 `/login.php` 發送表單登入，安全建立獨立 session。
     - 向 `/home/eService/homework/management/homeworklist/index.php` 抓取家課清單。
     - 堆疊式 `SimpleDOMParser` 支援深層巢狀 table 解析，精準識別 eClass 欄位（「限期」為截止日、「開始日期」為派發日、「學科」與「學科組別」）。
   - 業務過濾規則實測：
     - 李悅（P3）：100% 排除進階科（進階中文、進階英文、進階數學等）。
     - 李昕（P1）：無進階科分流，正確保留小一常識、英文等學科。
     - 日期分類：以「限期」計算剩餘天數，精準放入「今日必做」、「近幾日」、「測驗」或「其他」。
     - 長期紀錄保護：自動保留長期項目（如全年勤讀獎閱讀卡 20 張進度等），防止日常家課更新意外覆蓋。

3. **M3 雙寫真相與合規閘門**：
   - 實作 `scripts/update_status.py`，原子化雙寫 `status.json` 與 `DASHBOARD.md`。
   - 雙孩狀態嚴格隔離，無損保留既有獎勵點數與零食兌換目錄。
   - GitHub Actions 抓取後自動執行 `scripts/validate_status.py` 嚴格檢驗，若無變更不產生多餘提交，有變更則自動 commit & push 並驅動 GitHub Pages 更新。

4. **客觀驗收測試（202/202 100% Pass）**：
   - 本機與 CI 均能運行 `pytest`，涵蓋 Tier 1 功能測項（141 項）、Tier 2 邊界異常測項（44 項）、Tier 3 跨功能整合測項（5 項）、Tier 4 真實生活場景測項（12 項）。

## Git 分支與提交進度

- 當前分支：`main`
- 最新狀態：
  - 成功解決功課詳情提取問題：eClass 將詳細要求/範圍藏於標題欄 `<img title="...">` 提示屬性中。增強 `SimpleDOMParser` 支援解析 `img[title]` 與 `img[alt]`，成功提取口試題目（愛國愛澳）、常識水之探究生詞（10個）、Quiz 1 範疇（時態+閱讀理解）、勤讀獎指引，並標註「附件」圖示。
  - 家長總覽頁 `index.html` 同步新增 `.item-detail` 樣式與渲染，家長可在總覽直接檢視詳細範圍與說明。
  - 實測確認 Mr. Kelvin 數學習作 7 隨教師發布後已自動入庫。
  - 修正小孩看板積分漏洞：先前錯誤點擊完成後再取消未扣除積分。新增 `revokeForTask(child, key)` 與自動對齊函式 `reconcilePoints(child)`，取消勾選時即時扣回單項分與今日全清獎勵分，重新整理時自動校準清理先前誤點殘留之虛增積分。
  - 完成全系統深度排查與全面除錯（/boost）：
    1. 修正日期反向倒置：嚴格隔離 DD/MM（p1 > 12）與標準 MM/DD，並擴充點號分隔符支援（`17.9`、`2026.09.16`）。
    2. 增設 `syncNow()` 5 秒逾時 Promise 保護，杜絕網路斷線時無窮掛起。
    3. 修復平板端同步彈窗 Toast 隱形問題與重試按鈕反饋。
    4. 修正 `DASHBOARD.md` 閉環區塊日期推進邏輯，避免跨孩子污染與八進制跳脫衝突。
    5. 強化前端 `escapeHtml` XSS 轉義防護，統一快取版號至 `v=20260917-06`。
  - 平板載入與伺服器錯誤防護強化（v=20260917-07）：
    1. 實測確認 GitHub Pages 與 Firebase Realtime Database 連線 100% 正常（雙孩頁面無錯誤完整渲染）。
    2. 分析平板「Server Error」主因為 GitHub Actions 自動定時推送爬蟲時觸發之 GitHub Pages 30~60 秒邊界切換暫態，搭配 iPad Safari 強快取所致。
    3. `child.js` 與 `index.html` 全面防禦：`status.json` fetch 補齊 `!r.ok` 檢查與親切重試按鈕，`localStorage` 寫入全面以 `try...catch` 包裹防護 iPad 私密瀏覽與配額邊界異常，版號全面更新為 `v=20260917-07`。
  - 全套自動化回歸測試 212/212 測試全數通過（100% Pass）。

## 決策與紅線

- 零 AI 額度消耗：純代碼爬蟲 + GitHub Actions 自動化，不消耗任何大模型 Token。
- 禁止進 repo：密碼、OTP、session cookie、私鑰；任何帳密嚴格只存於 GitHub Secrets。
- 對使用者一律繁體中文。

## 接手順序

1. `MEMORY.md`（現況快照）
2. `AGENTS.md`（工作流程與自動化腳本指南）
3. `status.json`（優先）＋ `DASHBOARD.md`（功課真相雙寫）
4. `SOP.md`（快速指令參考）
5. 每次修改後必須跑雙重門禁：
   - `python3 scripts/validate_status.py`
   - `python3 tests/run_all_tests.py`

