# AGENTS.md — 培正 eClass 雙孩功課工作流

> 給任何 AI agent（Codex／Gemini／Claude／Grok／Cursor…）接手或二次開發用。  
> **禁止**把密碼、OTP、session cookie 寫進本 repo。登入憑證只走各執行環境的安全表單／密碼庫。  
> **溝通語言：與使用者溝通一律用繁體中文。**  
> 新接手先讀 `MEMORY.md`（現況快照），再讀本檔（工作流）。

| 資源 | URL |
|---|---|
| 人類看板（日曆＋甘特＋勾選） | https://samulee003.github.io/puiching-eclass-handoff/ |
| 機器讀取 JSON | https://samulee003.github.io/puiching-eclass-handoff/status.json |
| Repo | https://github.com/samulee003/puiching-eclass-handoff |
| eClass | https://eclass.puiching.edu.mo/templates/ |
| 家課路徑 | 登入後 → **資訊服務 → 家課表** |

時區：家長在 **Asia/Macau**；寫 `updated_at` 用 ISO UTC，顯示給家長用澳門時間。

---

## 1. 目標（一次結算）

每天（平日）產出兩孩「可行動」摘要，並同步公開看板：

1. 掃 eClass 家課表（含**不須繳交**）
2. 置頂「今日必做」
3. 更新 `status.json` **和** `DASHBOARD.md`（只改自己負責的孩子區塊）。小孩／家長網頁只讀 `status.json`；只改 Markdown 等於沒更新畫面。
4. 跑 `python3 scripts/validate_status.py`，通過後經 PR 合併到 `main` → GitHub Pages
5. 繁中短訊通知家長；家長回「清了」才閉環

家長偏好：**日曆／甘特**看進度（已在 `index.html`，預設摺疊）；待辦可勾選（localStorage，不回寫 GitHub）。
小孩平板用 `abigail.html`（李悅）／`gloria.html`（李昕）：勾選功課、積分換零食。

---

## 2. 角色與歸屬（一人一事）

| 孩子 | EN | 年級 | 執行者 | 瀏覽器 |
|---|---|---|---|---|
| **李悅** | Abigail | 小三 P3 | 劉備／Grok（或接手的主 agent） | **專用** profile，禁與李昕混登 |
| **李昕** | Gloria | 小一 P1 | 張飛／分派的執行 agent | **另一** profile，禁登李悅 |

協調者（君主／劉備職責）：

- 定方向、追交付、一次結算給家長
- **不**代替張飛登李昕；但必須盯李昕有無交摘要
- 謀略／節奏取捨可問軍師（孔明）；執行分派雲長／翼德

通訊節約：agent 之間只傳 **新令／阻塞改派／最終事實**；禁空轉 ACK。

---

## 3. 過濾規則（硬）

### 李悅

- **省略／忽略**一切「進階英語」「進階數學」及科目名含「進階」的項目（不是分區，是直接不當作家課）
- 口試／Quiz 等必須抓 **詳情內文**，不能只有標題

### 李昕

- 小一 **無進階 track**；摘要不必寫進階過濾語
- 成功登入頁面中文名必須是 **李昕**（不是李悅）

### 共同

- 「不須繳交」也要列（易漏，如 Spelling）
- **禁止虛構**家課；登入失敗就報 `LOGIN_REQUIRED`，不要編造
- 閉環：家長回「李悅清了」「李昕清了」或「兩個清了」

---

## 4. 定時節奏（甲案・省額）

| 何時 (Macau) | 誰 | 做什麼 |
|---|---|---|
| 平日 **15:30** | 李悅負責人 | 掃李悅 → 更新看板李悅區 → 通知 |
| 平日 **15:30** | 李昕負責人 | 掃李昕 → 更新看板李昕區 → 通知（或交協調者彙總） |
| 平日 **16:00** | 協調者 | 追交：缺誰追誰；兩邊齊可不吵家長 |
| 周日 **18:00** | 各負責人 | 週摘要 |
| ~~平日 17:30~~ | — | **已暫停**（省額） |

升級問家長：

- 同一孩 **連 2 次**掃描失敗，或
- 截止 **≤24h** 仍未做且掃不到詳情

勤讀獎（李悅中文）：eClass 寫全年 **20** 張閱讀卡、每週最多 **2**；進度由協調者週一提醒（家長曾說 15，以 eClass 20 為準除非家長改口）。

---

## 5. 單次掃描 SOP

### 自動化流程（推薦・最懶人・0 AI Token 額度）

本專案已建置 GitHub Actions 定時自動同步工作流，**平日每天 15:30（澳門時間）自動執行**，完全不消耗 Grok / AI Token 額度：

```bash
# 手動立即觸發 GitHub Actions 同步：
gh workflow run eclass-sync.yml

# 本機執行（讀取環境變數或 per-child 專用變數）：
export ECLASS_LI_YUE_USERNAME="p21528136"
export ECLASS_LI_YUE_PASSWORD="***"
export ECLASS_LI_XIN_USERNAME="p23528999"
export ECLASS_LI_XIN_PASSWORD="***"

python3 scripts/update_status.py --child li-yue --scrape
python3 scripts/update_status.py --child li-xin --scrape

# 離線測試（使用測試 fixture 模擬，無需真實連網）：
python3 scripts/update_status.py --child li-yue --fixture tests/fixtures/eclass_abigail_normal.html
python3 scripts/update_status.py --child li-xin --fixture tests/fixtures/eclass_gloria_normal.html
```

### 手動／瀏覽器流程（備援）

```
1. 開 https://eclass.puiching.edu.mo/templates/
2. 登入目標孩（或「某某家長」且已選對學生）
3. 核對身分：李悅 / 李昕 中文名正確
4. 資訊服務 → 家課表
5. 收集：科目、標題、截止、須繳交否、內容詳情、附件、發出人
6. 李悅：刪進階*
7. 分類：今日必做 / 近幾日 / 本週測驗 / 其他
8. 只覆寫 DASHBOARD.md 與 status.json 裡「自己的孩子」；同一孩子的兩邊內容必須一致
9. 跑 `python3 scripts/validate_status.py`，通過後再 commit
10. 開 PR 合併到 `main`（緊急才直接 push `main`）
11. 繁中 ADHD 短訊：下一步是什麼；請回「清了」
```

詳情頁打不開時：至少保留標題＋截止，並標「詳情未取到」。
遇到未登入或過期時：明確回報 `LOGIN_REQUIRED`，禁止編造虛假家課。

---

## 6. 登入與密碼策略（甲＋乙）

硬限制：

- Agent **看不到**安全表單送出的密碼（write-only）
- **禁止**明文密碼進聊天紀錄／本 repo／DASHBOARD
- 學校若要 OTP，**無法真正無人值守**；只能減少「翻密碼」

現行策略：

| 步驟 | 做法 |
|---|---|
| 甲 | 各孩 **分瀏覽器**；家長在該瀏覽器 **親手打一次** 帳密並讓 Chrome「儲存密碼」（安全表單程式填入通常 **不會** 觸發存密） |
| 乙 | 掃完 **不要亂清 cookie／關到掉 session**；有效期內少重登 |
| OTP | 仍要家長按；可約定 15:20–15:40 守 Student App |

已知現況（2026-09-14）：

- 李悅（劉備瀏覽器）：Chrome 已成功存過一筆（家長帳可開家課表選李悅）
- 李昕（張飛瀏覽器）：曾出現 Password Manager **無法持久化**（0 筆）→ 該 profile 過期仍走 **安全表單**，不要逼家長空存

Session 過期：`LOGIN_REQUIRED` → 對 **該孩所屬** agent 的對話出安全表單／交桌面；**禁止**交叉登入。

---

## 7. 看板資料契約

### `status.json`（優先給 agent）

- `schema_version`, `updated_at` (UTC ISO), `timezone`: `Asia/Macau`
- `children[]`: `id` (`li-yue`|`li-xin`), `en`, `zh`, `grade`, `owner`
- 區塊：`due_today`, `due_soon`, `tests_this_week`, `other`
- 每項：`subject`, `title`, `due` (`YYYY-MM-DD`), `submit_required` (bool), 可選 `note`/`detail`/`progress`
- `scan_schedule_macau`, `rules`, `ui`
- `cleared`: 僅家長閉環後改 true（或保持 false 由 localStorage 勾選）

### `DASHBOARD.md`

人類／agent 備援 Markdown；**只改自己負責區塊**，保留另一孩內容。

### `index.html`

- 讀 `status.json`
- 先顯示兩孩待辦清單；**日曆／時程**摺在下方
- 勾選預設存本機 `localStorage`（不回寫 repo）；頁尾「☁️ 雲端同步」可選接 Firebase 即時同步勾選＋積分
- 「清了」按鈕複製給家長貼回主 agent

### `abigail.html` / `gloria.html`

- 各孩平板自管頁；與家長頁共用 `puiching-eclass-todos-v1`（勾選）＋ `puiching-eclass-points-v1`（積分）
- 小孩頁不直接信任 `due_today`／`due_soon` 標籤：`assets/child.js` 會按澳門今天重算顯示桶（逾期／今天 → 今天要做，其餘未來 → 快到期；測驗／其他不動）
- 勾選賺積分，獎勵商店兌換實體零食（需家長兌現）
- 李昕頁（`gloria.html`）為較大字、無時程圖
- 頁尾「☁️ 雲端同步」與家長頁用同一組家庭同步碼，同步勾選＋積分（見 `SYNC_SETUP.md`）

### 同步鍵與不變量

- `puiching-eclass-todos-v1`：勾選；`puiching-eclass-points-v1`：積分
- `puiching-eclass-sync-code-v1`：家庭同步碼；`puiching-eclass-sync-pending-v1`：離線待送
- **極簡配對契約**：
  - URL 參數：支援 `?familyId=<CODE>`（或 `?sync=<CODE>`, `?familyCode=<CODE>`）。
  - 自動配對：小孩平板透過 QR Code 或點擊連結載入後，`sync.js` 自動寫入 LocalStorage 並觸發 Firebase 連線，隨後呼叫 `window.history.replaceState` 自動消除 URL 參數，避免同步碼外洩。
  - 狀態徽章：已同步 ☁️（雙向即時）、本機 💾（未配置或純離線模式）、離線 ⚠️（暫存中）、連線中 ⏳（認證中）。
  - 離線優先：斷網期間的操作會存入待發佇列，網路恢復後自動重播同步。
- 同步只寫勾選＋積分，**不回寫** `status.json`／`DASHBOARD.md`；功課真相仍由掃描更新

開發時改 UI／契約：開 PR 說明如何驗證 Pages；合併 `main` 後硬重新整理。

---

## 8. Git 發布流程

```bash
# 在本 repo 工作樹
# 1) 更新 status.json + DASHBOARD.md（必要時 index.html / abigail.html / gloria.html / assets/* / sync*）
# 2) 跑雙重驗證閘門：
python3 scripts/validate_status.py   # 驗證 status.json Schema 與日期合規
python3 tests/run_all_tests.py       # 執行 202 項 Tier 1~4 端對端與場景驗證

# 3) 檢查無密碼、無 cookie、無私鑰後發布：
git add status.json DASHBOARD.md index.html abigail.html gloria.html assets/child.js assets/child.css AGENTS.md MEMORY.md
git commit -m "Update eClass digest YYYY-MM-DD"
git push origin main
```

Pages 來源：`main` 根目錄。人類驗證：https://samulee003.github.io/puiching-eclass-handoff/

---

## 9. 回報家長（語氣）

- 繁體中文；ADHD：先「下一步」，少廢話
- 兩孩一次結算優於分開刷屏
- 額度緊時：減少 agent 互打、砍重複掃描、用本看板讓其他 AI 接手

範本：

```
【兩孩今日】
李悅：1) … 2) …
李昕：1) …
清完回「清了」。
看板：https://samulee003.github.io/puiching-eclass-handoff/
```

---

## 10. 建議二次開發方向（給外來 agent）

可開 PR 的方向（不破壞契約）：

1. `status.json` schema 版本化＋簡單 JSON Schema
2. 日曆／甘特：多月、匯出 ICS、逾期排序
3. ~~勾選＋積分 Firebase 同步~~（已實作：`scripts/setup_firebase.sh` 一鍵自動配置，家長端原生 SVG QR Code 免打字掃碼配對）
4. ~~自動從家課表 HTML 解析的測試夾具與抓取引擎~~（已實作：`scripts/scrape_eclass.py` 與 `fixtures/`）
5. ~~自動化端對端測試套件與合規閘門~~（已實作：`tests/run_all_tests.py` 共 202/202 測項 100% 通過）
6. 勤讀獎進度小工具（週上限 2／目標 20）
7. 修復／文件化「分 profile Chrome 密碼庫無法寫入」的替代方案（OS keyring／vault 注入），**仍禁止**把密寫進 git

不要做：

- 把密碼 commit 進 repo
- 合併兩孩登入到同一瀏覽器 session
- 發明家課內容充數
- 恢復高頻掃描拖垮額度（除非家長明示）

---

## 11. 快速檢查清單（接手 60 秒）

- [ ] 我負責李悅還是李昕？（瀏覽器／帳號不混）
- [ ] 先讀 `MEMORY.md`，再讀最新 `status.json`／`DASHBOARD.md`
- [ ] Session 活著？否則 `LOGIN_REQUIRED` 請家長
- [ ] 掃完只改自己的 JSON／MD 區塊，且兩邊一致（推薦使用 `scripts/update_status.py`）
- [ ] 跑 `python3 scripts/validate_status.py` 與 `python3 tests/run_all_tests.py` 通過
- [ ] PR 合併到 `main` 後硬重新整理 Pages，看日期與勾選是否正確
- [ ] 通知家長；等「清了」

---

## 12. 相關檔案

| 檔 | 用途 |
|---|---|
| `AGENTS.md` | 本工作流（給 agents） |
| `MEMORY.md` | 現況快照（先讀這個） |
| `SOP.md` | 單次掃描短步驟 |
| `README.md` | 人類＋agents 入口 |
| `status.json` | 機器真相 |
| `DASHBOARD.md` | Markdown 真相 |
| `index.html` | 家長總覽（待辦、日曆、原生 SVG QR Code 配對） |
| `abigail.html` | 李悅平板頁（支援 `?familyId=` 一鍵免打字配對） |
| `gloria.html` | 李昕平板頁（支援 `?familyId=` 一鍵免打字配對） |
| `assets/child.js` | 小孩頁共用邏輯（勾選＋積分） |
| `assets/qrcode.min.js` | 純前端原生 SVG QR Code 生成函式庫 |
| `sync.js` | 勾選＋積分跨裝置即時同步（Firebase RTDB，離線優雅降級） |
| `sync-config.js` | Firebase Web config（由 setup 腳本自動產生，禁止放私鑰／密碼） |
| `firebase.json` | Firebase 專案配置 |
| `firebase.rules.json` | Realtime Database 安全規則 |
| `scripts/setup_firebase.sh` | 一鍵自動配置 Firebase、啟用 RTDB 與寫入 config 腳本 |
| `scripts/scrape_eclass.py` | eClass 抓取過濾器（進階科目排除、口試詳情抽取、安全驗證） |
| `scripts/update_status.py` | 原子雙寫引擎（雙寫 `status.json` 與 `DASHBOARD.md`） |
| `scripts/validate_status.py` | 合規驗證器（檢查結構、欄位完整性與日期格式） |
| `tests/run_all_tests.py` | 4-Tier 202 項端對端綜合測試總套件 |
| `SYNC_SETUP.md` | 跨裝置同步設定 |

**最後更新說明：** 2026-09-16 — 全面打通 B+C 雙軌全自動懶人方案：完成 Firebase 一鍵自動設定與 SVG QR Code 免打字配對、eClass 家課表過濾抓取引擎、原子雙寫更新器，並經 202 項 E2E 測試 100% 驗證通過；`status.json`＋`DASHBOARD.md` 雙寫真相合規。
