# Frontend Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade document merging assistant frontend from basic CSS to Tailwind CSS v4 + shadcn/ui + framer-motion + Lucide icons in Apple/Linear minimal high-end style.

**Architecture:** Replace all CSS with Tailwind utility classes. Use shadcn/ui for interactive components (Button, Badge, Textarea, Card, Collapsible). framer-motion for animations. Lucide React for icons. Component tree stays the same: App → Header + ChatWindow (WelcomeScreen + ChatMessage[]) + ChatInput.

**Tech Stack:** React 19, Vite 8, Tailwind CSS v4, shadcn/ui, framer-motion, lucide-react

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `frontend/package.json` | Modify | Add dependencies |
| `frontend/vite.config.js` | Modify | Add Tailwind plugin |
| `frontend/index.html` | Modify | Add Inter font link |
| `frontend/src/index.css` | Rewrite | Tailwind directives + custom theme |
| `frontend/src/App.jsx` | Rewrite | New header, layout with Tailwind |
| `frontend/src/App.css` | **Delete** | Replaced by Tailwind |
| `frontend/src/components/WelcomeScreen.jsx` | **Create** | Welcome with quick-action cards |
| `frontend/src/components/ChatWindow.jsx` | Rewrite | Tailwind + framer-motion |
| `frontend/src/components/ChatMessage.jsx` | Rewrite | Tailwind + Lucide + framer-motion |
| `frontend/src/components/ChatInput.jsx` | Rewrite | Tailwind + Lucide + shadcn |
| `frontend/src/lib/utils.js` | **Create** | shadcn utility |
| `frontend/src/components/ui/button.jsx` | **Create** | shadcn Button |
| `frontend/src/components/ui/badge.jsx` | **Create** | shadcn Badge |
| `frontend/src/components/ui/textarea.jsx` | **Create** | shadcn Textarea |
| `frontend/src/components/ui/card.jsx` | **Create** | shadcn Card |
| `frontend/src/components/ui/collapsible.jsx` | **Create** | shadcn Collapsible |
| `frontend/components.json` | **Create** | shadcn config |

Remove legacy dead code:
| `frontend/src/components/FileList.jsx` | **Delete** | Unused |
| `frontend/src/components/ProgressPanel.jsx` | **Delete** | Unused |
| `frontend/src/components/ResultPanel.jsx` | **Delete** | Unused |
| `frontend/src/components/UploadZone.jsx` | **Delete** | Unused |

---

### Task 1: Install Dependencies

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Install npm packages**

Run:
```bash
cd /d/my_document_integration/frontend && npm install framer-motion lucide-react clsx tailwindcss @tailwindcss/vite tailwind-merge 2>&1
```

Expected: packages install successfully.

- [ ] **Step 2: Verify package.json updated**

Check that `frontend/package.json` now contains `framer-motion`, `lucide-react`, `clsx`, `tailwindcss`, `@tailwindcss/vite`, `tailwind-merge` in dependencies.

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: add Tailwind v4, shadcn/ui, framer-motion, lucide-react deps"
```

---

### Task 2: Configure Tailwind CSS v4 and Vite

**Files:**
- Modify: `frontend/vite.config.js`
- Create: `frontend/src/lib/utils.js`

- [ ] **Step 1: Add Tailwind plugin to Vite config**

Edit `frontend/vite.config.js`:

```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
    },
  },
})
```

Run to verify Vite starts without errors:
```bash
cd /d/my_document_integration/frontend && npx vite build --logLevel error 2>&1 | head -20
```

- [ ] **Step 2: Create shadcn utils file**

Create `frontend/src/lib/utils.js`:

```js
import { clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs) {
  return twMerge(clsx(inputs))
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/vite.config.js frontend/src/lib/utils.js
git commit -m "feat: configure Tailwind CSS v4 with Vite plugin and shadcn utils"
```

---

### Task 3: Create Tailwind Theme CSS

**Files:**
- Rewrite: `frontend/src/index.css`

- [ ] **Step 1: Replace index.css with Tailwind + custom theme**

Write `frontend/src/index.css`:

```css
@import "tailwindcss";

@theme {
  --color-brand: #0066FF;
  --color-brand-hover: #0052CC;
  --color-brand-light: color-mix(in srgb, #0066FF 8%, transparent);
  --color-success: #22C55E;
  --color-warning: #F59E0B;
  --color-error: #EF4444;

  --font-sans: 'Inter', system-ui, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
}

@layer base {
  body {
    @apply bg-[#FAFAFA] text-[#525252] antialiased;
    font-family: var(--font-sans);
    font-size: 15px;
    line-height: 1.6;
  }

  * {
    @apply border-[#E5E5E5];
  }
}

/* Scrollbar */
.chat-window::-webkit-scrollbar { width: 5px; }
.chat-window::-webkit-scrollbar-thumb { background: #E5E5E5; border-radius: 4px; }
```

- [ ] **Step 2: Verify Tailwind compiles**

Run:
```bash
cd /d/my_document_integration/frontend && npx vite build 2>&1 | tail -5
```

Expected: Build succeeds with no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/index.css
git commit -m "feat: add Tailwind theme with brand tokens and Inter font"
```

---

### Task 4: Add Inter Font and Update HTML

**Files:**
- Modify: `frontend/index.html`

- [ ] **Step 1: Add Inter and JetBrains Mono font links**

Edit `frontend/index.html` — add font links inside `<head>`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
    <title>Word文档智能合并工具</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/index.html
git commit -m "feat: add Inter and JetBrains Mono font loading"
```

---

### Task 5: Create shadcn/ui Components

**Files:**
- Create: `frontend/components.json`
- Create: `frontend/src/components/ui/button.jsx`
- Create: `frontend/src/components/ui/badge.jsx`
- Create: `frontend/src/components/ui/textarea.jsx`
- Create: `frontend/src/components/ui/card.jsx`
- Create: `frontend/src/components/ui/collapsible.jsx`

- [ ] **Step 1: Create components.json**

Write `frontend/components.json`:

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "default",
  "rsc": false,
  "tsx": false,
  "tailwind": {
    "config": "",
    "css": "src/index.css",
    "baseColor": "neutral",
    "cssVariables": false
  },
  "aliases": {
    "components": "src/components",
    "utils": "src/lib/utils"
  }
}
```

- [ ] **Step 2: Create Button component**

Write `frontend/src/components/ui/button.jsx`:

```jsx
import { cn } from "../../lib/utils"

const variants = {
  default: "bg-brand text-white hover:bg-brand-hover shadow-sm",
  ghost: "hover:bg-gray-100 text-gray-600",
  outline: "border border-gray-200 bg-white hover:bg-gray-50 text-gray-700",
  success: "bg-success text-white hover:bg-emerald-600 shadow-sm",
}

const sizes = {
  default: "h-10 px-4 py-2 rounded-[10px]",
  sm: "h-8 px-3 text-xs rounded-md",
  lg: "h-12 px-6 text-base rounded-[12px]",
  icon: "h-10 w-10 rounded-[10px]",
}

export default function Button({ className, variant = "default", size = "default", ...props }) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 font-medium text-sm transition-all duration-150 disabled:opacity-40 disabled:pointer-events-none cursor-pointer",
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    />
  )
}
```

- [ ] **Step 3: Create Badge component**

Write `frontend/src/components/ui/badge.jsx`:

```jsx
import { cn } from "../../lib/utils"

export default function Badge({ className, variant = "default", ...props }) {
  const variants = {
    default: "bg-brand/8 text-brand",
    secondary: "bg-gray-100 text-gray-600",
    success: "bg-emerald-50 text-emerald-700",
  }

  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-0.5 text-xs font-medium rounded-full",
        variants[variant],
        className
      )}
      {...props}
    />
  )
}
```

- [ ] **Step 4: Create Textarea component**

Write `frontend/src/components/ui/textarea.jsx`:

```jsx
import { cn } from "../../lib/utils"

export default function Textarea({ className, ...props }) {
  return (
    <textarea
      className={cn(
        "flex min-h-[40px] w-full rounded-[10px] border border-gray-200 bg-white px-3.5 py-2.5 text-[15px] placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-brand/30 focus:border-brand transition-shadow resize-none",
        "disabled:bg-gray-50 disabled:opacity-60",
        className
      )}
      {...props}
    />
  )
}
```

- [ ] **Step 5: Create Card component**

Write `frontend/src/components/ui/card.jsx`:

```jsx
import { cn } from "../../lib/utils"

export function Card({ className, ...props }) {
  return (
    <div
      className={cn(
        "rounded-[16px] border border-gray-100 bg-white p-5 shadow-[0_1px_2px_rgba(0,0,0,0.04),0_4px_16px_rgba(0,0,0,0.04)] transition-all duration-200",
        className
      )}
      {...props}
    />
  )
}

export function CardHeader({ className, ...props }) {
  return <div className={cn("flex flex-col gap-1", className)} {...props} />
}

export function CardTitle({ className, ...props }) {
  return <h3 className={cn("text-[15px] font-semibold text-gray-900", className)} {...props} />
}

export function CardDescription({ className, ...props }) {
  return <p className={cn("text-[13px] text-gray-400", className)} {...props} />
}

export function CardContent({ className, ...props }) {
  return <div className={cn("", className)} {...props} />
}
```

- [ ] **Step 6: Create Collapsible component**

Write `frontend/src/components/ui/collapsible.jsx`:

```jsx
import { useState, createContext, useContext } from "react"
import { cn } from "../../lib/utils"

const CollapsibleContext = createContext({ open: false, toggle: () => {} })

export function Collapsible({ defaultOpen = false, children, className }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <CollapsibleContext.Provider value={{ open, toggle: () => setOpen(v => !v) }}>
      <div className={cn("rounded-[12px] border border-gray-100 overflow-hidden", className)}>
        {children}
      </div>
    </CollapsibleContext.Provider>
  )
}

export function CollapsibleTrigger({ children, className, asChild }) {
  const { toggle } = useContext(CollapsibleContext)
  return (
    <div onClick={toggle} className={cn("cursor-pointer select-none", className)}>
      {children}
    </div>
  )
}

export function CollapsibleContent({ children, className }) {
  const { open } = useContext(CollapsibleContext)
  if (!open) return null
  return <div className={cn("border-t border-gray-100", className)}>{children}</div>
}
```

- [ ] **Step 7: Commit**

```bash
git add frontend/components.json frontend/src/components/ui/ frontend/src/lib/utils.js
git commit -m "feat: add shadcn/ui components (Button, Badge, Textarea, Card, Collapsible)"
```

---

### Task 6: Create WelcomeScreen Component

**Files:**
- Create: `frontend/src/components/WelcomeScreen.jsx`

- [ ] **Step 1: Write WelcomeScreen with quick-action cards**

Write `frontend/src/components/WelcomeScreen.jsx`:

```jsx
import { motion } from "framer-motion"
import { Upload, GitMerge, Download, FileText } from "lucide-react"

const cards = [
  { icon: Upload, title: "上传文档", desc: "支持 .docx 格式", action: "上传" },
  { icon: GitMerge, title: "AI 智能合并", desc: "语义识别共性内容", action: "合并" },
  { icon: Download, title: "下载文档", desc: "一键保存结果", action: "下载" },
]

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.08, delayChildren: 0.1 },
  },
}

const item = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 400, damping: 30 } },
}

export default function WelcomeScreen({ onCardClick }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-5 py-12">
      <motion.div
        initial={{ opacity: 0, y: -12, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ type: "spring", stiffness: 500, damping: 30 }}
        className="mb-8"
      >
        <div className="w-16 h-16 rounded-2xl bg-brand/8 flex items-center justify-center mb-6 mx-auto">
          <FileText className="w-8 h-8 text-brand" strokeWidth={1.5} />
        </div>
        <h2 className="text-[22px] font-semibold text-gray-900 text-center mb-2">
          文档合并助手
        </h2>
        <p className="text-[15px] text-gray-400 text-center max-w-[340px] leading-relaxed">
          上传多个 Word 文档，我会智能识别共性内容，生成高质量的合并文档
        </p>
      </motion.div>

      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="flex gap-3 max-w-[480px] w-full"
      >
        {cards.map((card) => (
          <motion.div
            key={card.action}
            variants={item}
            className="flex-1 bg-gray-50 hover:bg-gray-100/80 rounded-2xl p-4 cursor-pointer transition-colors duration-200 group"
            onClick={() => onCardClick?.(card.action)}
            whileHover={{ y: -2 }}
            whileTap={{ scale: 0.98 }}
          >
            <div className="w-8 h-8 rounded-lg bg-white shadow-sm flex items-center justify-center mb-3 group-hover:bg-brand group-hover:text-white transition-colors duration-200">
              <card.icon className="w-4 h-4" strokeWidth={1.5} />
            </div>
            <div className="text-[13px] font-semibold text-gray-800 mb-0.5">{card.title}</div>
            <div className="text-[11px] text-gray-400">{card.desc}</div>
          </motion.div>
        ))}
      </motion.div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/WelcomeScreen.jsx
git commit -m "feat: add WelcomeScreen with quick-action cards and animations"
```

---

### Task 7: Rewrite ChatMessage Component

**Files:**
- Rewrite: `frontend/src/components/ChatMessage.jsx`

- [ ] **Step 1: Rewrite ChatMessage with Tailwind, Lucide, framer-motion**

Write `frontend/src/components/ChatMessage.jsx`:

```jsx
import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { Wrench, Loader2, CheckCircle2, XCircle, Circle, ChevronDown, ChevronUp, RefreshCw, Brain, Download, FileText } from "lucide-react"
import { Card, CardHeader, CardTitle, CardContent } from "./ui/card"
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from "./ui/collapsible"
import Badge from "./ui/badge"
import Button from "./ui/button"

function formatSize(bytes) {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const messageVariants = {
  initial: { opacity: 0, y: 4 },
  animate: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 500, damping: 30 } },
}

function AnalysisPanel({ analysis }) {
  const [expandedThoughts, setExpandedThoughts] = useState({})

  if (!analysis || !analysis.steps || analysis.steps.length === 0) return null

  const toggleThoughts = (heading) => {
    setExpandedThoughts(prev => ({ ...prev, [heading]: !prev[heading] }))
  }

  const doneCount = analysis.steps.filter(s => s.status === 'done').length
  const errorCount = analysis.steps.filter(s => s.status === 'error').length

  return (
    <Collapsible defaultOpen className="mt-3 border-l-2 border-l-brand">
      <CollapsibleTrigger className="flex items-center gap-2.5 px-3 py-2.5 hover:bg-gray-50">
        <Brain className="w-4 h-4 text-brand" strokeWidth={1.5} />
        <span className="text-[13px] font-semibold text-gray-800 flex-1">
          AI 语义分析 ({doneCount}/{analysis.steps.length})
        </span>
        <div className="flex gap-1.5">
          {errorCount > 0 && <Badge variant="secondary" className="text-[11px] text-red-600 bg-red-50">{errorCount} 失败</Badge>}
        </div>
        <ChevronDown className="w-3.5 h-3.5 text-gray-300 chevron-icon" />
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="max-h-80 overflow-y-auto">
          {analysis.steps.map((step, i) => (
            <div
              key={step.heading || i}
              className={`px-3 py-2.5 border-b border-gray-50 last:border-0 ${step.status === 'running' ? 'bg-amber-50/50' : ''}`}
            >
              <div className="flex items-center gap-2">
                {step.status === 'running' && <Loader2 className="w-3.5 h-3.5 text-amber-500 animate-spin flex-shrink-0" strokeWidth={2.5} />}
                {step.status === 'done' && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 flex-shrink-0" strokeWidth={2} />}
                {step.status === 'error' && <XCircle className="w-3.5 h-3.5 text-red-500 flex-shrink-0" strokeWidth={2} />}
                {!step.status && <Circle className="w-3.5 h-3.5 text-gray-300 flex-shrink-0" strokeWidth={1.5} />}

                <span className="text-[12px] text-gray-700 flex-1 truncate" title={step.heading}>
                  {step.heading.split(' > ').pop() || step.heading}
                </span>

                {step.retry && (
                  <span className="inline-flex items-center gap-1 text-[11px] text-amber-600 bg-amber-50 border border-amber-200 px-1.5 py-px rounded">
                    <RefreshCw className="w-3 h-3" strokeWidth={2} />
                    {step.retry.attempt}
                  </span>
                )}

                {step.thoughts && step.thoughts.length > 0 && (
                  <button
                    className="text-[11px] text-brand hover:bg-brand/8 px-1.5 py-px rounded transition-colors flex-shrink-0 cursor-pointer"
                    onClick={(e) => { e.stopPropagation(); toggleThoughts(step.heading); }}
                  >
                    {expandedThoughts[step.heading] ? '收起' : '思考'}
                  </button>
                )}
              </div>

              {step.error && (
                <div className="text-[11px] text-red-600 mt-1.5 ml-5.5 px-2 py-1 bg-red-50 rounded">{step.error}</div>
              )}

              <AnimatePresence>
                {expandedThoughts[step.heading] && step.thoughts && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="mt-2 ml-5.5 pl-2.5 border-l-2 border-brand/20 overflow-hidden"
                  >
                    {step.thoughts.map((t, j) => (
                      <div key={j} className="text-[12px] text-gray-500 leading-relaxed py-0.5 whitespace-pre-wrap break-words">
                        {t}
                      </div>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          ))}
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}

export default function ChatMessage({ msg }) {
  const isUser = msg.role === 'user'

  return (
    <motion.div
      variants={messageVariants}
      initial="initial"
      animate="animate"
      className={`flex gap-2 ${isUser ? 'justify-end' : 'justify-start'} ${isUser ? 'ml-auto max-w-[75%]' : 'mr-auto max-w-[85%]'}`}
    >
      <div className={isUser
        ? "bg-brand text-white rounded-2xl rounded-br-md px-4 py-2.5 text-[14px] leading-relaxed shadow-sm"
        : "bg-gray-100 text-gray-600 rounded-2xl rounded-bl-md px-4 py-2.5 text-[14px] leading-relaxed"
      }>
        {/* File chips */}
        {msg.files && msg.files.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-2">
            {msg.files.map((f, i) => (
              <span key={i} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[12px] ${isUser ? 'bg-white/20 text-white' : 'bg-white text-gray-600 shadow-sm'}`}>
                <FileText className="w-3 h-3" strokeWidth={1.5} />
                <span className="max-w-[140px] truncate">{f.filename || f.name}</span>
                {f.size && <span className="opacity-60">{formatSize(f.size)}</span>}
              </span>
            ))}
          </div>
        )}

        {/* Text content */}
        {msg.content && (
          <div className={isUser ? "text-white" : "message-text"}>
            {isUser ? (
              msg.content
            ) : (
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
            )}
          </div>
        )}

        {/* Tool call indicator */}
        {msg.toolCall && (
          <div className="flex items-center gap-2 mt-2 px-2.5 py-1.5 bg-amber-50 border border-amber-100 rounded-lg text-[12px] text-amber-700">
            <Loader2 className="w-3.5 h-3.5 animate-spin" strokeWidth={2} />
            <span className="font-medium">正在执行：{msg.toolCall.label}</span>
          </div>
        )}

        {/* Progress bar */}
        {msg.progress && (
          <div className="mt-2">
            <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-brand rounded-full transition-all duration-500 ease-out"
                style={{ width: `${Math.min(msg.progress.percent || 0, 100)}%` }}
              />
            </div>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-[11px] text-gray-400">{msg.progress.message}</span>
              {msg.progress.stage && (
                <Badge variant="default">{msg.progress.stage.toUpperCase()}</Badge>
              )}
            </div>
          </div>
        )}

        {/* AI Analysis panel */}
        {msg.analysis && <AnalysisPanel analysis={msg.analysis} />}

        {/* Result card */}
        {msg.result && msg.result.download_url && (
          <div className="mt-3 p-4 bg-emerald-50 border border-emerald-100 rounded-2xl">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-7 h-7 rounded-lg bg-emerald-100 flex items-center justify-center">
                <FileText className="w-4 h-4 text-emerald-600" strokeWidth={1.5} />
              </div>
              <span className="text-[14px] font-semibold text-gray-800">
                {msg.result.filename || '合并文档.docx'}
              </span>
            </div>
            {msg.result.summary && (
              <div className="flex gap-4 mb-3 text-[12px] text-gray-500">
                <span>{msg.result.summary.common_sections || 0} 共性章节</span>
                <span>{msg.result.summary.doc_specific_total || 0} 独有内容</span>
                <span>{msg.result.summary.total_docs || 0} 份文档</span>
              </div>
            )}
            <Button
              variant="success"
              size="lg"
              className="w-full"
              onClick={() => {
                const a = document.createElement('a');
                a.href = msg.result.download_url;
                a.download = msg.result.filename || 'merged.docx';
                a.click();
              }}
            >
              <Download className="w-4 h-4" strokeWidth={1.5} />
              下载合并文档
            </Button>
          </div>
        )}

        {/* Timestamp */}
        <div className={`text-[11px] mt-2 ${isUser ? 'text-white/60' : 'text-gray-400'}`}>
          {new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
        </div>
      </div>
    </motion.div>
  )
}
```

Note: Also update `frontend/src/index.css` — append at the bottom for markdown message styling:

```css
.message-text h1, .message-text h2, .message-text h3 {
  font-size: 15px;
  font-weight: 600;
  margin: 6px 0 4px;
  color: #262626;
}
.message-text hr { border: none; border-top: 1px solid #E5E5E5; margin: 8px 0; }
.message-text blockquote {
  border-left: 2px solid #0066FF;
  padding-left: 10px;
  color: #737373;
  margin: 6px 0;
}
.message-text ul, .message-text ol { padding-left: 20px; margin: 4px 0; }
.message-text li { margin-bottom: 2px; }
.message-text code {
  background: #F5F5F5;
  padding: 1px 4px;
  border-radius: 4px;
  font-size: 13px;
  font-family: var(--font-mono);
}
.message-text strong { font-weight: 600; color: #262626; }
.message-text table {
  width: 100%;
  border-collapse: collapse;
  margin: 10px 0;
  font-size: 13px;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 0 0 1px #E5E5E5;
}
.message-text thead { background: #F5F5F5; }
.message-text thead th {
  padding: 8px 12px;
  text-align: left;
  font-weight: 600;
  color: #262626;
  border-bottom: 2px solid #E5E5E5;
  font-size: 12px;
}
.message-text tbody td {
  padding: 7px 12px;
  border-bottom: 1px solid #F5F5F5;
  vertical-align: top;
}
.message-text tbody tr:last-child td { border-bottom: none; }
.message-text tbody tr:nth-child(even) { background: #FAFAFA; }
.message-text tbody tr:hover { background: #0066FF08; }
.message-text td:first-child, .message-text th:first-child { padding-left: 14px; }
.message-text td:last-child, .message-text th:last-child { padding-right: 14px; }
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ChatMessage.jsx frontend/src/index.css
git commit -m "feat: rewrite ChatMessage with Tailwind, Lucide icons, framer-motion"
```

---

### Task 8: Rewrite ChatWindow Component

**Files:**
- Rewrite: `frontend/src/components/ChatWindow.jsx`

- [ ] **Step 1: Rewrite ChatWindow with Tailwind + framer-motion**

Write `frontend/src/components/ChatWindow.jsx`:

```jsx
import { useEffect, useRef } from "react"
import { motion } from "framer-motion"
import ChatMessage from "./ChatMessage"
import WelcomeScreen from "./WelcomeScreen"

export default function ChatWindow({ messages, isProcessing, onQuickAction }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-4 chat-window">
      {messages.length === 0 ? (
        <WelcomeScreen onCardClick={onQuickAction} />
      ) : (
        messages.map((msg, idx) => (
          <ChatMessage key={idx} msg={msg} />
        ))
      )}

      {isProcessing && (
        <div className="flex justify-start">
          <div className="bg-gray-100 rounded-2xl rounded-bl-md px-4 py-3">
            <div className="flex gap-1">
              {[0, 1, 2].map(i => (
                <motion.span
                  key={i}
                  className="w-[7px] h-[7px] rounded-full bg-gray-400"
                  animate={{ y: [0, -5, 0] }}
                  transition={{ duration: 1.4, repeat: Infinity, delay: i * 0.2, ease: "easeInOut" }}
                />
              ))}
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ChatWindow.jsx
git commit -m "feat: rewrite ChatWindow with Tailwind, framer-motion typing dots"
```

---

### Task 9: Rewrite ChatInput Component

**Files:**
- Rewrite: `frontend/src/components/ChatInput.jsx`

- [ ] **Step 1: Rewrite ChatInput with Tailwind, shadcn, Lucide**

Write `frontend/src/components/ChatInput.jsx`:

```jsx
import { useRef, useState, useCallback } from "react"
import { Paperclip, ArrowUp, Loader2 } from "lucide-react"
import Textarea from "./ui/textarea"
import Button from "./ui/button"

export default function ChatInput({ onSend, onUpload, disabled, hasFiles }) {
  const [text, setText] = useState('')
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef(null)

  const handleSend = useCallback(() => {
    const trimmed = text.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setText('')
  }, [text, disabled, onSend])

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }, [handleSend])

  const handleFileChange = useCallback(async (e) => {
    const files = Array.from(e.target.files || [])
    if (files.length === 0) return

    setUploading(true)
    try {
      const fileData = await Promise.all(
        files.map(async (file) => {
          const buf = await file.arrayBuffer()
          const bytes = new Uint8Array(buf)
          let binary = ''
          for (let i = 0; i < bytes.length; i++) {
            binary += String.fromCharCode(bytes[i])
          }
          return { filename: file.name, content: btoa(binary) }
        })
      )
      onUpload(fileData)
    } catch (err) {
      alert(`文件上传失败: ${err.message}`)
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }, [onUpload])

  return (
    <div className="border-t border-gray-100 px-4 py-3 bg-white flex-shrink-0">
      <div className="flex items-end gap-2 max-w-[740px] mx-auto">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled || uploading}
          title="上传文档"
        >
          {uploading ? (
            <Loader2 className="w-5 h-5 animate-spin" strokeWidth={1.5} />
          ) : (
            <Paperclip className="w-5 h-5 text-gray-400" strokeWidth={1.5} />
          )}
        </Button>

        <input
          ref={fileInputRef}
          type="file"
          accept=".docx"
          multiple
          onChange={handleFileChange}
          className="hidden"
        />

        <Textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={hasFiles ? '描述你的合并需求，或直接说"合并"...' : '上传文档后，描述你的合并需求...'}
          rows={1}
          disabled={disabled}
          className="flex-1"
        />

        <Button
          variant="default"
          size="icon"
          onClick={handleSend}
          disabled={disabled || !text.trim()}
          title="发送"
        >
          <ArrowUp className="w-5 h-5" strokeWidth={2} />
        </Button>
      </div>

      {hasFiles && (
        <div className="text-center mt-2 text-[11px] text-gray-400">
          Enter 发送，Shift+Enter 换行
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ChatInput.jsx
git commit -m "feat: rewrite ChatInput with shadcn/ui Button/Textarea, Lucide icons"
```

---

### Task 10: Rewrite App.jsx

**Files:**
- Rewrite: `frontend/src/App.jsx`

- [ ] **Step 1: Rewrite App with new Header and layout**

Write `frontend/src/App.jsx`:

```jsx
import { useState, useEffect, useCallback } from 'react'
import ChatWindow from './components/ChatWindow'
import ChatInput from './components/ChatInput'
import Badge from './components/ui/badge'

const API_BASE = '/api'

const TOOL_LABELS = {
  get_session_info: '查看文档状态',
  parse_documents: '解析文档',
  get_document_detail: '查看文档详情',
  analyze_commonality: 'AI语义分析',
  generate_merged_document: '生成合并文档',
}

export default function App() {
  const [sessionId, setSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const [isProcessing, setIsProcessing] = useState(false)
  const [uploadedFiles, setUploadedFiles] = useState([])

  useEffect(() => {
    fetch(`${API_BASE}/chat/start`, { method: 'POST' })
      .then(r => r.json())
      .then(data => setSessionId(data.session_id))
      .catch(err => console.error('Failed to create session:', err))
  }, [])

  const addMessage = useCallback((msg) => {
    setMessages(prev => [...prev, msg])
  }, [])

  const handleQuickAction = useCallback((action) => {
    if (action === '上传') {
      document.querySelector('input[type="file"]')?.click()
    } else if (action === '合并') {
      handleSend('合并这些文档')
    } else if (action === '下载') {
      // Find last result with download_url and trigger download
      const lastResult = [...messages].reverse().find(m => m.result?.download_url)
      if (lastResult) {
        const a = document.createElement('a')
        a.href = lastResult.result.download_url
        a.download = lastResult.result.filename || 'merged.docx'
        a.click()
      }
    }
  }, [messages])

  const handleUpload = useCallback(async (fileData) => {
    if (!sessionId) { alert('会话尚未建立，请稍后再试'); return }

    try {
      const res = await fetch(`${API_BASE}/chat/${sessionId}/upload`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ files: fileData }),
      })
      if (!res.ok) { const err = await res.json(); throw new Error(err.detail || '上传失败') }

      const data = await res.json()
      addMessage({ role: 'user', content: `上传了 ${data.added} 个文档`, files: fileData.map(f => ({ filename: f.filename })) })
      setUploadedFiles(prev => [...prev, ...fileData.map(f => f.filename)])

      addMessage({
        role: 'agent',
        content: `已接收 ${data.added} 个文档，当前共 **${data.total_files}** 个文档。\n\n${data.total_files >= 2
            ? '文档数量已满足合并条件。你可以：\n- 说"合并这些文档"开始合并\n- 问我关于文档的问题\n- 告诉我你的特殊需求'
            : `还需要至少 **${2 - data.total_files}** 个文档才能合并，请继续上传。`
          }`,
      })
    } catch (err) {
      addMessage({ role: 'agent', content: `❌ 上传失败：${err.message}` })
    }
  }, [sessionId, addMessage])

  const handleSend = useCallback(async (text) => {
    if (!sessionId || isProcessing) return
    addMessage({ role: 'user', content: text })
    setIsProcessing(true)

    try {
      const res = await fetch(`${API_BASE}/chat/${sessionId}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      })
      if (!res.ok) { const err = await res.json(); throw new Error(err.detail || '请求失败') }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let streamedContent = ''
      let streamedProgress = null
      let streamedResult = null

      const upsertAgentMsg = (updates) => {
        setMessages(prev => {
          const copy = [...prev]
          const last = copy[copy.length - 1]
          if (last && last.role === 'agent' && last._streaming) {
            Object.assign(last, updates)
          } else {
            copy.push({ role: 'agent', _streaming: true, ...updates })
          }
          return copy
        })
      }

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        let eventType = ''
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim()
          } else if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              switch (eventType) {
                case 'message':
                  streamedContent += (streamedContent ? '\n\n' : '') + data.text
                  upsertAgentMsg({ content: streamedContent, progress: streamedProgress, result: streamedResult })
                  break

                case 'tool_call': {
                  const toolName = data.tool || ''
                  const label = TOOL_LABELS[toolName] || toolName
                  setMessages(prev => {
                    const copy = [...prev]
                    const last = copy[copy.length - 1]
                    if (last && last.role === 'agent' && last._streaming) last.toolCall = { name: toolName, label }
                    return copy
                  })
                  break
                }

                case 'progress':
                  streamedProgress = data
                  upsertAgentMsg({ progress: data })
                  break

                case 'analysis_step':
                  setMessages(prev => {
                    const copy = [...prev]
                    const last = copy[copy.length - 1]
                    if (last && last.role === 'agent' && last._streaming) {
                      if (!last.analysis) last.analysis = { steps: [], totalGroups: 0, completedGroups: 0 }
                      last.analysis.totalGroups = data.total || 0
                      last.analysis.completedGroups = data.status === 'done' ? (last.analysis.completedGroups + 1) : (data.current || 0)
                      const existingIdx = last.analysis.steps.findIndex(s => s.heading === data.heading)
                      const step = { heading: data.heading, status: data.status, error: data.error || '', thoughts: [] }
                      if (existingIdx >= 0) { step.thoughts = last.analysis.steps[existingIdx].thoughts; last.analysis.steps[existingIdx] = step }
                      else last.analysis.steps.push(step)
                    }
                    return copy
                  })
                  break

                case 'thinking':
                  setMessages(prev => {
                    const copy = [...prev]
                    const last = copy[copy.length - 1]
                    if (last && last.role === 'agent' && last._streaming) {
                      if (!last.analysis) last.analysis = { steps: [], totalGroups: 0, completedGroups: 0 }
                      const step = last.analysis.steps.find(s => s.heading === data.heading)
                      if (step) step.thoughts.push(data.thought || '')
                      else last.analysis.steps.push({ heading: data.heading, status: 'running', error: '', thoughts: [data.thought || ''] })
                    }
                    return copy
                  })
                  break

                case 'retry':
                  setMessages(prev => {
                    const copy = [...prev]
                    const last = copy[copy.length - 1]
                    if (last && last.role === 'agent' && last._streaming) {
                      if (!last.analysis) last.analysis = { steps: [], totalGroups: 0, completedGroups: 0 }
                      const step = last.analysis.steps.find(s => s.heading === data.heading)
                      if (step) step.retry = { attempt: data.attempt, reason: data.reason }
                    }
                    return copy
                  })
                  break

                case 'result':
                  streamedResult = data
                  setMessages(prev => {
                    const copy = [...prev]
                    for (let i = copy.length - 1; i >= 0; i--) {
                      if (copy[i].role === 'agent') {
                        copy[i]._streaming = false
                        copy[i].toolCall = null
                        copy[i].progress = null
                        copy[i].analysis = null
                        copy[i].result = data
                        if (data.message) copy[i].content = data.message
                        return copy
                      }
                    }
                    return copy
                  })
                  break

                case 'error':
                  setMessages(prev => {
                    const copy = [...prev]
                    const last = copy[copy.length - 1]
                    if (last && last.role === 'agent' && last._streaming) {
                      last._streaming = false
                      last.content = `❌ ${data.message}`
                    } else copy.push({ role: 'agent', content: `❌ ${data.message}` })
                    return copy
                  })
                  break
              }
            } catch (e) { /* skip parse errors */ }
          }
        }
      }

      setMessages(prev => {
        const copy = [...prev]
        const last = copy[copy.length - 1]
        if (last && last.role === 'agent' && last._streaming) {
          last._streaming = false
          last.toolCall = null
          last.analysis = null
        }
        return copy
      })
    } catch (err) {
      addMessage({ role: 'agent', content: `❌ 处理失败：${err.message}` })
    } finally {
      setIsProcessing(false)
    }
  }, [sessionId, isProcessing, addMessage])

  return (
    <div className="h-screen flex flex-col max-w-[740px] mx-auto bg-white shadow-[0_0_0_1px_rgba(0,0,0,0.04),0_1px_3px_rgba(0,0,0,0.06)]">
      {/* Header */}
      <header className="flex items-center gap-3 h-[52px] px-5 border-b border-gray-100 flex-shrink-0 bg-white">
        <div className="w-2.5 h-2.5 rounded-full bg-brand flex-shrink-0" />
        <span className="text-[15px] font-semibold text-gray-900">文档合并助手</span>
        {uploadedFiles.length > 0 && (
          <Badge variant="default" className="ml-auto">
            {uploadedFiles.length} 份文档
          </Badge>
        )}
      </header>

      <ChatWindow
        messages={messages}
        isProcessing={isProcessing}
        onQuickAction={handleQuickAction}
      />

      <ChatInput
        onSend={handleSend}
        onUpload={handleUpload}
        disabled={isProcessing || !sessionId}
        hasFiles={uploadedFiles.length > 0}
      />
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat: rewrite App with Tailwind header, Badge, WelcomeScreen integration"
```

---

### Task 11: Cleanup — Delete Legacy Files

**Files:**
- Delete: `frontend/src/App.css`
- Delete: `frontend/src/components/UploadZone.jsx`
- Delete: `frontend/src/components/FileList.jsx`
- Delete: `frontend/src/components/ProgressPanel.jsx`
- Delete: `frontend/src/components/ResultPanel.jsx`

- [ ] **Step 1: Delete legacy files**

```bash
rm /d/my_document_integration/frontend/src/App.css
rm /d/my_document_integration/frontend/src/components/UploadZone.jsx
rm /d/my_document_integration/frontend/src/components/FileList.jsx
rm /d/my_document_integration/frontend/src/components/ProgressPanel.jsx
rm /d/my_document_integration/frontend/src/components/ResultPanel.jsx
```

- [ ] **Step 2: Verify build**

Run:
```bash
cd /d/my_document_integration/frontend && npx vite build 2>&1 | tail -10
```

Expected: Build succeeds, no errors, no warnings about missing files.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.css frontend/src/components/UploadZone.jsx frontend/src/components/FileList.jsx frontend/src/components/ProgressPanel.jsx frontend/src/components/ResultPanel.jsx
git commit -m "chore: remove legacy CSS and unused card-based UI components"
```

---

### Task 12: Final Verification

- [ ] **Step 1: Build check**

```bash
cd /d/my_document_integration/frontend && npx vite build 2>&1
```

Expected: Clean build with no errors or warnings.

- [ ] **Step 2: Start dev server and check visually**

```bash
cd /d/my_document_integration/frontend && npm run dev 2>&1 &
```

Open the dev URL in browser. Verify:
- Header renders with blue dot + title + document badge
- Welcome screen shows 3 quick-action cards with animations
- Upload flow works: file chips appear in user messages
- AI messages render with markdown formatting
- Analysis panel: collapsible, shows step status, thoughts toggle
- Result card: download button styled correctly
- Input area: shadcn buttons, textarea with focus ring
- Typing indicator: animated dots while processing
- Empty input: send button disabled (opacity)
- Responsive: layout works at various widths

- [ ] **Step 3: Commit any final tweaks**

```bash
git add .
git commit -m "chore: final verification tweaks and cleanup"
```
