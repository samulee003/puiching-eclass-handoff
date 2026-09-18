---
name: Pui Ching eClass Family System
colors:
  surface: '#121927'
  surface-dim: '#090d16'
  surface-bright: '#172133'
  surface-container-lowest: '#090d16'
  surface-container-low: '#0f172a'
  surface-container: '#121927'
  surface-container-high: '#1c2637'
  surface-container-highest: '#243247'
  on-surface: '#f1f5f9'
  on-surface-variant: '#94a3b8'
  outline: 'rgba(255, 255, 255, 0.08)'
  outline-variant: 'rgba(255, 255, 255, 0.14)'
  primary: '#3b82f6'
  on-primary: '#ffffff'
  primary-container: '#1d4ed8'
  on-primary-container: '#93c5fd'
  secondary: '#ec4899'
  on-secondary: '#ffffff'
  secondary-container: '#be185d'
  on-secondary-container: '#f9a8d4'
  tertiary: '#10b981'
  on-tertiary: '#ffffff'
  tertiary-container: '#059669'
  on-tertiary-container: '#a7f3d0'
  error: '#f43f5e'
  on-error: '#ffffff'
  error-container: '#881337'
  on-error-container: '#fecdd3'
  star-gold: '#f59e0b'
  background: '#090d16'
  on-background: '#f1f5f9'
typography:
  display:
    fontFamily: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Noto Sans TC", sans-serif
    fontSize: 1.55rem
    fontWeight: '800'
    lineHeight: 2rem
    letterSpacing: -0.01em
  headline-lg:
    fontFamily: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Noto Sans TC", sans-serif
    fontSize: 1.4rem
    fontWeight: '800'
    lineHeight: 1.75rem
  headline-md:
    fontFamily: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Noto Sans TC", sans-serif
    fontSize: 1.25rem
    fontWeight: '800'
    lineHeight: 1.6rem
  headline-sm:
    fontFamily: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Noto Sans TC", sans-serif
    fontSize: 1.15rem
    fontWeight: '700'
    lineHeight: 1.5rem
  body-lg:
    fontFamily: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Noto Sans TC", sans-serif
    fontSize: 1rem
    fontWeight: '500'
    lineHeight: 1.5rem
  body-md:
    fontFamily: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Noto Sans TC", sans-serif
    fontSize: 0.92rem
    fontWeight: '500'
    lineHeight: 1.4rem
  body-sm:
    fontFamily: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Noto Sans TC", sans-serif
    fontSize: 0.84rem
    fontWeight: '500'
    lineHeight: 1.3rem
  label-md:
    fontFamily: ui-monospace, "SF Mono", "Cascadia Code", monospace
    fontSize: 0.82rem
    fontWeight: '600'
    lineHeight: 1.2rem
rounded:
  sm: 6px
  DEFAULT: 12px
  md: 18px
  lg: 24px
  xl: 28px
  full: 9999px
spacing:
  gutter: 18px
  margin: 20px
  card-gap: 14px
  section-gap: 24px
---

# Design System: 培正 eClass 雙孩學習看板與自律平台 (Pui Ching eClass Family System)

## 1. Visual Theme & Atmosphere

- **家長總覽看板 (Parent Dashboard)**:
  - **Atmosphere**: 精緻、冷靜且高資訊密度的沉浸式工作台 (Atmosphere: Cockpit Balanced, Density: 6, Variance: 5, Motion: 5)。以深色黑曜石畫布為底，藉由層次分明的半透明毛玻璃表面與細微邊界營造出專業、井井有條的現代軟體儀表板質感。
  - **Emotional Tone**: 條理、放心、清晰掌控。家長一瞥即可掌握雙孩當日必做、小測驗與本週時程。

- **小孩專屬自律平板頁面 (Child Tablet UI - Abigail 李悅 & Gloria 李昕)**:
  - **Atmosphere**: 陽光、鼓勵、觸感鮮明且現代化的自律成就空間 (Atmosphere: Playful Studio, Density: 4, Variance: 6, Motion: 6)。告別低俗卡通配色，採用高雅明亮的自然純白底色，搭配專屬個性色彩（Abigail: 蔚藍海風 Ocean Sapphire；Gloria: 活力櫻花 Sakura Rose）。
  - **Emotional Tone**: 成就感、專注、儀式感。每一項任務打勾都有彈性微動態與星星閃爍，讓孩子享受完成家課並累積點數兌換小賣部零食的樂趣。

---

## 2. Color Palette & Roles

### 2.1 家長看板深色調系統 (Dark Slate System)
- **Canvas Obsidian** (`#090d16`): 主背景畫布，深邃深藍黑，減少夜間視覺疲勞。
- **Elevated Card Surface** (`#131a26`): 主卡片與面板背景，提供第一層立體維度。
- **Sub-Surface Tier** (`#1c2637`): 嵌套欄位、標籤與進度條軌道底色。
- **Glass Border** (`rgba(255, 255, 255, 0.08)`): 1px 微發光細邊框，界定結構且不搶視覺。
- **Text Primary High-Contrast** (`#f1f5f9`): 主標題與關鍵家課項目文字。
- **Text Muted Slate** (`#94a3b8`): 次要中繼資料、截止時間、說明備註。
- **Accent Abigail (P3 李悅)** (`#3b82f6`): 代表智慧與清晰的湛藍色。
- **Accent Gloria (P1 李昕)** (`#ec4899`): 代表溫暖與活力的甜粉色。
- **Functional Emerald** (`#10b981`): 完成、全數交齊、雲端連線正常。
- **Functional Amber** (`#f59e0b`): 今日必做、快到期提醒、待注意事項。
- **Functional Rose/Crimson** (`#f43f5e`): 逾期警告、必須繳交警示標籤。

### 2.2 小孩平板明亮自律系統 (Kid Light System)
- **Kid Canvas (Abigail)** (`#f0f7ff`): 淡淡的晴空柔藍底色。
- **Kid Canvas (Gloria)** (`#fff1f6`): 淡淡的櫻粉晨光底色。
- **Pure Card Surface** (`#ffffff`): 任務卡片底色，純白高對比。
- **Tactile Border** (`#e2e8f0`): 2px 圓潤卡片外框，提供清晰點擊邊界。
- **Done Background** (`#ecfdf5`): 任務完成後的清爽薄荷綠微底。
- **Done Border** (`#a7f3d0`): 任務完成後的邊框顏色。
- **Star Gold** (`#f59e0b`): 積分金星主色，象徵努力換來的榮譽。
- **Text Dark Navy** (`#0f172a`): 小孩大字體專用高對比深色，保護兒童視力。

---

## 3. Typography Architecture

- **Primary Font Stack**:
  - `system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Noto Sans TC", sans-serif`
  - 小孩頁面引入圓角無襯線優先：`ui-rounded, "PingFang SC Rounded", "Noto Sans TC", sans-serif`
- **Monospace Stack (數字與日期)**:
  - `ui-monospace, "SF Mono", "Cascadia Code", "JetBrains Mono", monospace`
- **Hierarchy & Scale**:
  - **Header Display**: 家長端 1.4rem (font-weight: 800)；小孩端 1.6rem - 2.0rem (font-weight: 800)。
  - **Section Title**: 1.05rem - 1.2rem (font-weight: 700)，搭配專屬 Emoji 或圖標導引。
  - **Task Title**: 1.05rem (家長端) / 1.15rem - 1.25rem (小孩端)，確保小一小三孩童容易認讀。
  - **Metadata & Chips**: 0.75rem - 0.85rem (font-weight: 600)，清楚膠囊藥丸設計。
- **Banned Typography**:
  - 嚴禁使用過於瘦長、難以辨識的細體或花體字。
  - 嚴禁純粹只有大小變化而無層次權重對比的設計。

---

## 4. Component Stylings & Behaviors

### 4.1 雙孩切換與統計進度條 (Dual Progress Cards)
- 頂部呈現雙孩當前完成度卡片，帶有圓角平滑漸變進度條（Abigail 藍綠漸變、Gloria 粉橙漸變）。
- 附帶「已完成 / 總數」動態數值與鼓勵小語（如「全數完成，超棒！🌟」或「加油，還剩 2 樣！」）。

### 4.2 任務卡片 (Interactive Task Cards)
- **小孩端**:
  - 最小點擊高度 60px (Gloria 達到 72px)，適合手指輕易觸控。
  - 左側配備 42x42px 超大圓角勾選方塊，未選時為純白外框，點選後轉為鮮明綠色搭配流暢白色對勾彈出動態。
  - 右側內容包含學科標籤 (如 `[中文]`, `[英文]`)、家課標題、截止時間膠囊、以及「須繳交」/「只需認讀」狀態標籤。
  - 卡片點擊提供 `-1px translateY` 觸感回饋，打勾後標題呈現輕度刪折線與優雅淡化。
- **家長端**:
  - 雙欄網格或自適應折疊，包含「今日必做」、「近幾日」、「測驗」、「其他」四大語意分組。
  - 提供即時過濾與高亮，支援「複製今日摘要」一鍵複製給家人群組。

### 4.3 獎勵小賣部 (Snack Shop)
- 4 欄 (桌面/平板) 或 2 欄 (手機) 零食兌換櫥窗卡片。
- 每張卡片展示大圖標、零食名稱、消耗星星數 (`50 ⭐`)。
- 餘額足夠時按鈕呈現醒目 Accent 色且具備微浮動提示；餘額不足時按鈕呈現優雅 disabled 鎖定狀態。
- 兌換成功時觸發灑花/滿天星微動態與 Toast 通知。

### 4.4 日曆與甘特時程視圖 (Calendar & Gantt Engine)
- **日曆 (Calendar)**:
  - 7 欄月曆網格，今日以高對比外框突顯。
  - 每日格子內以彩色圓點標示李悅 (藍點) 與李昕 (粉點) 的待辦項目，紅框標記逾期。
  - 點擊特定日期即刻展開下方當日清單細項，支援快捷聚焦。
- **時程 (Gantt)**:
  - 橫向滑動時間軸，具有今日時間紅線指標。
  - 條狀色塊按孩童分色，圓角膠囊呈現，完成項目以低透明度區隔。

### 4.5 雲端同步與免打字配對面板 (Cloud Sync & Pairing Panel)
- 折疊式現代狀態卡，包含「已同步 ☁️」、「本機模式 💻」、「連接中…」、「已離線 ⚠️」四態動態膠囊標籤。
- 一鍵展開即時產出純前端 SVG QR Code，小孩平板掃描即可完成配對，完全無資安外洩。

---

## 5. Motion Philosophy & Micro-Interactions

- **Spring Physics**: 所有互動狀態切換採用彈簧手感 (`cubic-bezier(0.34, 1.56, 0.64, 1)` 或 `cubic-bezier(0.4, 0, 0.2, 1)`)。
- **Tactile Push**: 按鈕在 `:active` 時縮小至 `scale(0.98)` 或 `translateY(1px)`，營造真實按鈕按壓質感。
- **Progress Fill**: 進度條具備 `transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1)` 平滑延伸。
- **Celebration Feedback**: 點擊「我做完了！🎉」或全選完成時，觸發輕量級慶祝動畫。

---

## 6. Anti-Patterns (Banned AI Clichés)

1. ❌ 嚴禁破壞任何既有測試所依賴的 DOM ID、Class 或結構：
   - `#sync-panel[data-sync-role="parent"]` / `[data-sync-role="child"]` 必須完好無損。
   - `#points`, `#progress-count`, `#encourage`, `#bar-fill`, `#updated`, `#sections`, `#tl`, `#shop`, `#btn-done`, `#toast` 必須全部保留。
   - `assets/child.js`, `assets/child.css`, `sync.js`, `sync-config.js` 引用結構不可變動。
2. ❌ 嚴禁使用刺眼的高飽和紫色/青色霓虹漸變與刺眼外發光。
3. ❌ 嚴禁純黑背景 (`#000000`)，一律採用深石板藍或黑曜石色階。
4. ❌ 嚴禁破壞雙寫機制與 `status.json` schema。
5. ❌ 嚴禁引入外部未授權的網路字型或大型肥大庫，確保極速秒開與離線支援。
