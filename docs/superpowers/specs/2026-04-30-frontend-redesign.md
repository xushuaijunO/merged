# Frontend Redesign — 极简高端风格

**Date**: 2026-04-30
**Status**: Approved

## Goal

将文档合并助手前端从基础 CSS 风格升级为 Apple/Linear 风格的极简高端设计。

## Scope

- 引入 Tailwind CSS v4 + shadcn/ui
- 使用 framer-motion 动画
- Lucide Icons 替代 emoji
- 浅色主题（仅浅色）
- 组件结构保持，样式全量重写

---

## Design Tokens

### Colors

| Token | Value | Usage |
|-------|-------|-------|
| brand | `#0066FF` | 按钮、链接、active 态 |
| brand-hover | `#0052CC` | 按钮 hover |
| brand-light | `#0066FF/0.08` | 选中背景 |
| success | `#22C55E` | 下载按钮、完成状态 |
| warning | `#F59E0B` | 进行中状态 |
| error | `#EF4444` | 错误状态 |
| gray-50 | `#FAFAFA` | 页面背景 |
| gray-100 | `#F5F5F5` | AI 气泡、hover 背景 |
| gray-200 | `#E5E5E5` | 边框 |
| gray-400 | `#A3A3A3` | placeholder |
| gray-500 | `#737373` | secondary text |
| gray-600 | `#525252` | body text |
| gray-900 | `#262626` | headings |

### Typography

- **Font**: Inter (headings + body), JetBrains Mono (code), system-ui fallback for CJK
- **Scale**: 12/13/14/15/16/20/24/32px
- **Body**: 15px, line-height 1.6, `#525252`

### Spacing

4 / 8 / 12 / 16 / 20 / 24 / 32 / 48px

### Border Radius

- Tight: 6px (small elements)
- Standard: 10px (buttons, inputs, cards)
- Large: 16px (message bubbles)
- Pill: 9999px (badges)

### Shadows

- Card: `0 1px 2px rgba(0,0,0,0.04), 0 4px 16px rgba(0,0,0,0.04)`
- Hover: `0 1px 2px rgba(0,0,0,0.06), 0 8px 24px rgba(0,0,0,0.08)`

---

## Layout

```
┌─────────────────────────────────────────────┐
│  Header: logo + title ............ doc badge │
├─────────────────────────────────────────────┤
│  Chat Window                                │
│  ┌───────────────────────────────────────┐  │
│  │ Welcome: icon + title + 3 quick cards │  │
│  │ Messages: user(right) / AI(left)      │  │
│  │   - markdown content                  │  │
│  │   - analysis panel (accordion)        │  │
│  │   - result card (download)            │  │
│  └───────────────────────────────────────┘  │
├─────────────────────────────────────────────┤
│  Input: [attach] [textarea] [send]         │
└─────────────────────────────────────────────┘
```

- `max-width: 740px` centered, white background
- No sidebar — single-column focus
- Ample whitespace, low information density

---

## Components

### Header
- Height 52px, bottom border `gray-100`
- Left: brand-colored dot + "文档合并助手" (16px, 600 weight)
- Right: document count pill badge (brand-light bg, brand text)

### Welcome Screen
Shown when no messages exist:
- Large Lucide icon (FileText, 48px)
- Title + description
- 3 quick-action cards in a horizontal row:
  - Upload (Upload icon, "上传文档", "支持 .docx 格式")
  - Merge (GitMerge icon, "AI 智能合并", "语义识别共性内容")
  - Download (Download icon, "下载文档", "一键保存结果")
- Cards: gray-50 bg, hover lifts 2px with deeper shadow

### Chat Messages
- **User**: brand bg, white text, right-aligned, max-w 75%, radius 16px br-6px
- **AI**: gray-100 bg, gray-600 text, left-aligned, max-w 85%, radius 16px bl-6px
- No avatar circles — clean bubble-only style
- Consecutive same-role messages: 8px gap
- Different-role messages: 20px gap
- Timestamp (hh:mm) in small gray below bubble

### Analysis Panel
- Collapsible accordion with left blue bar
- Header: icon + "AI 语义分析 (3/5)" + status tags + chevron
- Step rows: status dot (running/spinning, done/green-check, error/red-x) + heading text
- Thought bubbles: collapsible per-step, blue left-border block

### Result Card
- Light green bg, green border
- Title + stats row (common sections, unique content, source docs)
- Full-width download button (green, Lucide Download icon)

### Chat Input
- Row: attach button (40×40, gray-100) + textarea + send button (40×40, brand)
- Textarea: auto-height 1-4 rows, placeholder text, focus ring `ring-2 ring-brand/30`
- Hint text below: "Enter 发送，Shift+Enter 换行" (11px, gray-400)
- Send button disabled state: `opacity-40`

---

## Animations (framer-motion)

- Message entry: `y: 4 → 0`, `opacity: 0 → 1`, spring transition
- Quick card hover: `y: 0 → -2`, shadow deepens
- Analysis step completion: scale pop (0.6 → 1.15 → 1)
- Accordion expand: height spring
- Typing indicator: staggered dot bounce (1.4s loop with 0.2s delay per dot)

---

## Dependencies to Add

```
tailwindcss @tailwindcss/vite  (Tailwind v4 for Vite 8)
framer-motion                  (animations)
lucide-react                   (icons)
shadcn/ui components:
  - Button, Badge, Card, Textarea, Separator, Collapsible
```

## Files to Change

| File | Action |
|------|--------|
| `index.html` | Add Inter font link |
| `src/index.css` | Replace with Tailwind directives |
| `src/App.jsx` | Rebuild with Tailwind classes, header redesign |
| `src/App.css` | **Delete** — replaced by Tailwind |
| `src/components/ChatWindow.jsx` | Rebuild with Tailwind + framer-motion |
| `src/components/ChatMessage.jsx` | Rebuild with Tailwind + Lucide icons |
| `src/components/ChatInput.jsx` | Rebuild with Tailwind + Lucide icons |
| `src/components/WelcomeScreen.jsx` | **New** — welcome with quick action cards |
| `vite.config.js` | Add Tailwind plugin |
