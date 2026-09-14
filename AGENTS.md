# AGENTS.md — 培正 eClass 雙孩功課工作流

> 給任何 AI agent（Codex／Gemini／Claude／Grok／Cursor…）接手或二次開發用。  
> **禁止**把密碼、OTP、session cookie 寫進本 repo。登入憑證只走各執行環境的安全表單／密碼庫。

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
3. 更新 `status.json` + `DASHBOARD.md`（只改自己負責的孩子區塊）
4. 推到 `main` → GitHub Pages
5. 繁中短訊通知家長；家長回「清了」才閉環

家長偏好：**日曆／甘特**看進度（已在 `index.html`）；待辦可勾選（localStorage，不回寫 GitHub）。

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

```
1. 開 https://eclass.puiching.edu.mo/templates/
2. 登入目標孩（或「某某家長」且已選對學生）
3. 核對身分：李悅 / 李昕 中文名正確
4. 資訊服務 → 家課表
5. 收集：科目、標題、截止、須繳交否、內容詳情、附件、發出人
6. 李悅：刪進階*
7. 分類：今日必做 / 近幾日 / 本週測驗 / 其他
8. 只覆寫 DASHBOARD.md 與 status.json 裡「自己的孩子」
9. git commit + push main（或開 PR 後合併）
10. 繁中 ADHD 短訊：下一步是什麼；請回「清了」
```

詳情頁打不開時：至少保留標題＋截止，並標「詳情未取到」。

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
- 分頁：**日曆**（Macau today、李悅藍／李昕粉）＋**時程甘特**（今日→截止）
- 勾選存 **localStorage**（不回寫 repo）
- 「清了」按鈕複製給家長貼回主 agent

開發時改 UI／契約：開 PR 說明如何驗證 Pages；合併 `main` 後硬重新整理。

---

## 8. Git 發布流程

```bash
# 在本 repo 工作樹
# 1) 更新 status.json + DASHBOARD.md（必要時 index.html）
# 2) 檢查：無密碼、無 cookie
git add status.json DASHBOARD.md index.html AGENTS.md
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
3. 勾選狀態可選同步（需家長同意；預設仍 localStorage）
4. 自動從家課表 HTML 解析的測試夾具（fixtures，無真實密碼）
5. GitHub Action：validate `status.json` on PR
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
- [ ] 讀最新 `status.json`／`DASHBOARD.md`
- [ ] Session 活著？否則 `LOGIN_REQUIRED` 請家長
- [ ] 掃完只改自己的 JSON／MD 區塊
- [ ] Push 後打開 Pages 看日曆點是否落在正確日期
- [ ] 通知家長；等「清了」

---

## 12. 相關檔案

| 檔 | 用途 |
|---|---|
| `AGENTS.md` | 本工作流（給 agents） |
| `SOP.md` | 單次掃描短步驟 |
| `README.md` | 人類＋agents 入口 |
| `status.json` | 機器真相 |
| `DASHBOARD.md` | Markdown 真相 |
| `index.html` | 日曆／甘特／勾選 UI |

**最後更新說明：** 2026-09-14 — 雙軌甲案、密碼甲＋乙、Pages 日曆＋甘特、17:30 暫停、勤讀獎 eClass=20。
