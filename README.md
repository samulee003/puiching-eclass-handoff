# 培正 eClass 功課看板（人類 + Agents）

**人類網頁：** https://samulee003.github.io/puiching-eclass-handoff/  
**Agents JSON：** https://samulee003.github.io/puiching-eclass-handoff/status.json  
**Repo：** https://github.com/samulee003/puiching-eclass-handoff

## 兩種展示頁

- **家長 DASHBOARD：** `index.html` — 看兩孩全局進度、日曆、甘特圖，並複製「清了」訊息。
- **小孩平板學習頁：** `kids.html` — 選擇李悅或李昕，以可愛的任務板練習「待開始 → 進行中 → 完成啦」。

兩頁共用 `status.json` 和本機完成勾選；小孩頁的「開始任務／完成任務」會同步家長頁的勾選狀態，不會把資料寫回 GitHub。可用 `kids.html?child=li-yue` 或 `kids.html?child=li-xin` 直接開指定小孩的任務板。

## 給 Codex／Gemini

先讀 **`AGENTS.md`**（整套工作流），再讀 `status.json`（優先）或 `DASHBOARD.md` + `SOP.md`。  
李悅＝Abigail（略過所有進階*）；李昕＝Gloria（小一、無進階）。  
路徑：eClass → 資訊服務 → 家課表。密碼登入時給，勿寫進 repo。

## 給家長

打開上方網頁，看「今日必做」；做完回 Grok「李悅清了／李昕清了」。

## 檔案

| 檔 | 對象 |
|---|---|
| `index.html` | 家長 DASHBOARD |
| `kids.html` | 小孩平板用可愛專案管理頁 |
| `status.json` | Agent 機器讀取 |
| `DASHBOARD.md` | 人類／agent 備援 |
| `SOP.md` | 操作步驟 |
| `AGENTS.md` | **整套工作流（給任何 agent 開發／接手）** |
