# MEMORY.md — 培正 eClass 功課看板現況快照

更新日期：2026-09-16（Asia/Macau）。改行為或改資料的 agent 必須同步更新本檔日期與受影響段落。

## 一句話現況

全自動「懶人整合方案」（B+C）已全面完工！包含 Firebase 自動化腳本與免打字 QR Code 配對、eClass 家課表自動抓取與年級過濾、原子雙寫引擎，且 175 項端對端測試 100% 全數通過。

## 核心里程碑完成狀況

1. **M1 雲端同步與免打字配對**：
   - 實作 `scripts/setup_firebase.sh` 自動化配置 Realtime Database、匿名驗證與寫入 `sync-config.js`。
   - `index.html` 內建原生 SVG QR Code 卡片與家庭連結產出。
   - 兩孩平板頁面（`abigail.html` / `gloria.html`）支援讀取 `?familyId=` 參數實現零打字一鍵配對，未連線自動平滑降級為本機模式。
2. **M2 eClass 自動抓取引擎**：
   - 實作 `scripts/scrape_eclass.py`，支援環境變數帳密傳遞與離線測試夾具（`tests/fixtures/`）。
   - 嚴格落實李悅（P3）100% 排除進階科目、李昕（P1）無進階分流。
   - 口試／Quiz 詳情完整抽取，會話失效時安全拋出 `LOGIN_REQUIRED`。
3. **M3 雙寫真相與合規閘門**：
   - 實作 `scripts/update_status.py`，原子化雙寫 `status.json` 與 `DASHBOARD.md`。
   - 雙孩狀態嚴格隔離，無損保留既有獎勵點數與零食兌換目錄。
   - 強制串接 `scripts/validate_status.py` 驗證閘門。
4. **客觀驗收測試**：
   - `tests/run_all_tests.py` 共 175 個端對端測項（Tier 1–4），已達到 **175/175 通過（100% Pass）**。

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
