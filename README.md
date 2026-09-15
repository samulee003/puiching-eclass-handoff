# 培正 eClass 功課看板（人類 + Agents）

**人類網頁：** https://samulee003.github.io/puiching-eclass-handoff/  
**Agents JSON：** https://samulee003.github.io/puiching-eclass-handoff/status.json  
**Repo：** https://github.com/samulee003/puiching-eclass-handoff

## 頁面

- **家長總覽：** `index.html` — 兩孩待辦、複製「清了」；日曆／時程可展開
- **李悅平板：** `abigail.html`
- **李昕平板：** `gloria.html`

三頁共用 `status.json`；勾選預設存在本機瀏覽器，不回寫 GitHub。
要跨裝置即時同步勾選＋積分，見 [`SYNC_SETUP.md`](SYNC_SETUP.md)接 Firebase（選用，未設定照常用）。

## 給 Codex／Gemini

先讀 **`AGENTS.md`**（整套工作流），再讀 `status.json`（優先）或 `DASHBOARD.md` + `SOP.md`。  
李悅＝Abigail（略過所有進階*）；李昕＝Gloria（小一、無進階）。  
路徑：eClass → 資訊服務 → 家課表。密碼登入時給，勿寫進 repo。

## 給家長

打開上方網頁，看「今日必做」；做完回 Grok「李悅清了／李昕清了」。

## 檔案

| 檔 | 對象 |
|---|---|
| `index.html` | 家長總覽 |
| `abigail.html` | 李悅平板 |
| `gloria.html` | 李昕平板 |
| `status.json` | Agent 機器讀取 |
| `DASHBOARD.md` | 人類／agent 備援 |
| `SOP.md` | 操作步驟 |
| `SYNC_SETUP.md` | 跨裝置同步設定（選用） |
| `AGENTS.md` | **整套工作流（給任何 agent 開發／接手）** |
