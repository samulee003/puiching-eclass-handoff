# MEMORY.md — 培正 eClass 功課看板現況快照

更新日期：2026-09-16（Asia/Macau）。改行為或改資料的 agent 必須同步更新本檔日期與受影響段落。

## 一句話現況

全自動「懶人整合方案」（B+C）已全面完工並通過終局稽核！包含 Firebase 一鍵自動化設定腳本、家長端純前端原生 SVG QR Code 與免打字配對、eClass 家課表過濾抓取引擎、原子雙寫更新器，且 4-Tier 202 項端對端測試 100% 全數通過。

## 核心里程碑完成狀況

1. **M1 雲端同步與免打字配對（已全線打通上線）**：
   - 透過 Firebase CLI / Management API 完成真實雲端環境配置：
     - 專案：`puiching-eclass`
     - 資料庫：`puiching-eclass-default-rtdb`（位於 `asia-southeast1`）
     - 認證方式：已成功啟用匿名認證（Anonymous Authentication）
     - 安全性規則：已部署 `firebase.rules.json` 至雲端 RTDB
     - Web App：已建立 `puiching-web` 並將正式客戶端 Config 寫入 `sync-config.js`
     - 雲端實測：經由 Node 腳本對真實 Firebase 執行匿名登入、寫入合規驗證、讀取與清理，**100% 雙向即時同步驗證成功**！
   - `index.html` 內建原生 SVG QR Code 向量產出（`assets/qrcode.min.js`，零外部 API 依賴、無資安外洩風險）。
   - 兩孩平板頁面（`abigail.html` / `gloria.html`）支援讀取 `?familyId=`、`?sync=` 等參數實現零打字一鍵配對，載入後自動清除網址列參數。
   - 離線優先架構：未連線自動平滑降級為本機模式，斷網操作自動寫入本機佇列，連線恢復時依序重播。
2. **M2 eClass 自動抓取引擎**：
   - 實作 `scripts/scrape_eclass.py`，支援環境變數帳密傳遞與離線測試夾具（`tests/fixtures/`）。
   - 嚴格落實李悅（P3）100% 排除進階科目、李昕（P1）無進階分流。
   - 口試／Quiz 詳情完整抽取，會話失效、密碼錯誤或逾期時安全拋出 `LOGIN_REQUIRED`。
3. **M3 雙寫真相與合規閘門**：
   - 實作 `scripts/update_status.py`，原子化雙寫 `status.json` 與 `DASHBOARD.md`。
   - 雙孩狀態嚴格隔離，無損保留既有獎勵點數與零食兌換目錄。
   - 強制串接 `scripts/validate_status.py` 驗證閘門。
4. **客觀驗收測試（202/202 100% Pass）**：
   - `tests/run_all_tests.py` 涵蓋 Tier 1 功能測項（141 項）、Tier 2 邊界異常測項（44 項）、Tier 3 跨功能整合測項（5 項）、Tier 4 真實生活場景測項（12 項）。
   - 所有測項直連生產腳本，達到 **202/202 通過（100% Pass，耗時約 1.2 秒）**。

## Git 分支與提交進度

- 當前分支：`cursor/setup-dev-environment-29da`
- 關鍵 Commits：
  - `e84dcae`: Complete lazy integration (Option D): Firebase automation, QR pairing, eClass scraper, dual-writer & 175 E2E tests
  - `d752916`: Address gate audit: expand login failure indicators, add familyId param, and solidify assertions
  - `066cd02`: Finalize test suite: 202 E2E tests verified and passing (100% clean audit)
  - （本提交）: docs: update AGENTS.md and MEMORY.md with lazy automation toolchain and 202 E2E test suite

## 待確認與後續事項

1. 今日兩孩閉環皆「待回」（家長確認完成後可由家長點擊看板複製閉環回報）。
2. PR 合併時機（可透過 GitHub PR 合併至 `main` 分支以更新 GitHub Pages）。
3. 勤讀獎進度：李悅全年目標 20 本，每週上限 2 本，依週一提醒追蹤。

## 決策與紅線

- 版面保持乾淨：次要資訊摺疊，不搶待辦
- 積分採每孩 last-write-wins：正常每孩只有自己的平板會寫分
- 禁止進 repo：密碼、OTP、session cookie、私鑰；同步碼也不公開
- 對使用者一律繁體中文，先講下一步

## 接手順序

1. `MEMORY.md`（現況快照）
2. `AGENTS.md`（工作流程與自動化腳本指南）
3. `status.json`（優先）＋ `DASHBOARD.md`（功課真相雙寫）
4. `SOP.md`（快速指令參考）
5. 每次修改後必須跑雙重門禁：
   - `python3 scripts/validate_status.py`
   - `python3 tests/run_all_tests.py`

