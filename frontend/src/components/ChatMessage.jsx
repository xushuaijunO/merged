import { useState, useEffect, useRef } from "react"
import { motion, AnimatePresence } from "framer-motion"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { Loader2, CheckCircle2, XCircle, Circle, ChevronDown, RefreshCw, Brain, Download, FileText, X, Sparkles } from "lucide-react"
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from "./ui/collapsible"
import Badge from "./ui/badge"
import AnimatedNumber from "./AnimatedNumber"

function formatSize(bytes) {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const TOOL_DESCRIPTIONS = {
  get_session_info: '正在查看文档状态...',
  parse_documents: '正在解析文档结构，提取章节内容...',
  get_document_detail: '正在获取文档详情...',
  analyze_commonality: '正在识别多份文档的共性章节与独有内容...',
  generate_merged_document: '正在生成合并文档，整合封面目录与内容...',
}

function getToolDescription(toolName) {
  return TOOL_DESCRIPTIONS[toolName] || '正在处理...'
}

const messageVariants = {
  initial: { opacity: 0, y: 4 },
  animate: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 500, damping: 30 } },
}

function AnalysisPanel({ analysis }) {
  const [expandedThoughts, setExpandedThoughts] = useState({})
  const [panelOpen, setPanelOpen] = useState(true)
  const prevAllDone = useRef(false)

  const allDone = analysis.steps.length > 0 && analysis.steps.every(s => s.status === 'done')
  const hasRunning = analysis.steps.some(s => s.status === 'running')

  useEffect(() => {
    if (allDone && !prevAllDone.current) {
      const timer = setTimeout(() => setPanelOpen(false), 1000)
      prevAllDone.current = true
      return () => clearTimeout(timer)
    }
    if (hasRunning) {
      setPanelOpen(true)
      prevAllDone.current = false
    }
  }, [allDone, hasRunning])

  if (!analysis || !analysis.steps || analysis.steps.length === 0) return null

  const toggleThoughts = (heading) => {
    setExpandedThoughts(prev => ({ ...prev, [heading]: !prev[heading] }))
  }

  const doneCount = analysis.steps.filter(s => s.status === 'done').length
  const totalCount = analysis.totalGroups || analysis.steps.length
  const errorCount = analysis.steps.filter(s => s.status === 'error').length

  return (
    <Collapsible defaultOpen className="mt-3 border-l-2 border-l-brand overflow-hidden" open={panelOpen} onOpenChange={setPanelOpen}>
      <CollapsibleTrigger className="flex items-center gap-2.5 px-3 py-2.5 hover:bg-gray-50">
        {allDone ? (
          <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0" strokeWidth={2} />
        ) : (
          <Brain className="w-4 h-4 text-brand flex-shrink-0" strokeWidth={1.5} />
        )}
        <span className="text-[13px] font-semibold text-gray-800 flex-1 min-w-0 truncate">
          {allDone
            ? `AI 语义分析完成 (${doneCount}/${totalCount})`
            : `AI 语义分析 (${doneCount}/${totalCount})`
          }
        </span>
        <div className="flex gap-1.5">
          {errorCount > 0 && <Badge variant="secondary" className="text-[11px] text-red-600 bg-red-50">{errorCount} 失败</Badge>}
        </div>
        <ChevronDown className="w-3.5 h-3.5 text-gray-300" />
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

                <span className="text-[12px] text-gray-700 flex-1 min-w-0 truncate" title={step.heading}>
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

export default function ChatMessage({ msg, onRemoveFile }) {
  const isUser = msg.role === 'user'

  return (
    <motion.div
      variants={messageVariants}
      initial="initial"
      animate="animate"
      className={`flex gap-2 ${isUser ? 'justify-end' : 'justify-start'} ${isUser ? 'ml-auto max-w-[75%]' : 'mr-auto max-w-[85%]'}`}
    >
      <div className={isUser
        ? "bg-brand text-white rounded-2xl rounded-br-md px-4 py-2.5 text-[14px] leading-relaxed shadow-sm min-w-0 overflow-hidden"
        : "bg-gray-100 text-gray-600 rounded-2xl rounded-bl-md px-4 py-2.5 text-[14px] leading-relaxed min-w-0 overflow-hidden"
      }>
        {msg.files && msg.files.length > 0 && (
          <div className="flex flex-col gap-2 mb-2">
            {msg.files.map((f, i) => (
              <div
                key={i}
                className={`flex items-center gap-3 p-2.5 rounded-xl border ${isUser ? 'border-white/20 bg-white/10' : 'border-gray-200/60 bg-white/80'}`}
              >
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${isUser ? 'bg-white/20' : 'bg-brand/8'}`}>
                  <FileText className={`w-4 h-4 ${isUser ? 'text-white' : 'text-brand'}`} strokeWidth={1.5} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className={`text-[13px] font-medium truncate ${isUser ? 'text-white' : 'text-gray-700'}`}>
                    {f.filename || f.name}
                  </div>
                  <div className={`text-[11px] ${isUser ? 'text-white/60' : 'text-gray-400'}`}>
                    {formatSize(f.size)}
                  </div>
                </div>
                {onRemoveFile && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      onRemoveFile(f.filename || f.name)
                    }}
                    className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 cursor-pointer transition-colors ${isUser ? 'hover:bg-white/20 text-white/60 hover:text-white' : 'hover:bg-red-50 hover:text-red-500 text-gray-300'}`}
                  >
                    <X className="w-3.5 h-3.5" strokeWidth={2} />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        {msg.content && (
          <div className={isUser ? "text-white" : "message-text"}>
            {isUser ? (
              msg.content
            ) : (
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  table: ({ children, ...props }) => (
                    <div className="table-wrap">
                      <table {...props}>{children}</table>
                    </div>
                  ),
                  pre: ({ children, ...props }) => (
                    <pre {...props} style={{ overflowX: 'auto' }}>{children}</pre>
                  ),
                }}
              >{msg.content}</ReactMarkdown>
            )}
          </div>
        )}

        {msg.toolCall && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center gap-3 mt-2 px-3 py-2.5 bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-100/60 rounded-xl"
          >
            <motion.div
              animate={{ scale: [1, 1.15, 1] }}
              transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
              className="flex-shrink-0"
            >
              <Sparkles className="w-4 h-4 text-amber-500" strokeWidth={1.5} />
            </motion.div>
            <span className="text-[12px] text-amber-700 font-medium">
              {getToolDescription(msg.toolCall.name)}
            </span>
          </motion.div>
        )}

        {msg.progress && (
          <div className="mt-2">
            <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ease-out shadow-[0_0_6px_rgba(0,102,255,0.25)] ${msg._streaming ? 'progress-fill-shimmer' : 'bg-brand'}`}
                style={{ width: `${Math.min(msg.progress.percent || 0, 100)}%` }}
              />
            </div>
            <div className="flex items-center gap-2 mt-1 min-w-0">
              <span className="text-[11px] text-gray-400 truncate">{msg.progress.message}</span>
              {msg.progress.stage && (
                <Badge variant="default">{msg.progress.stage.toUpperCase()}</Badge>
              )}
            </div>
          </div>
        )}

        {msg.analysis && <AnalysisPanel analysis={msg.analysis} />}

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
                <span>
                  <AnimatedNumber value={msg.result.summary.common_sections || 0} duration={1.2} /> 共性章节
                </span>
                <span>
                  <AnimatedNumber value={msg.result.summary.doc_specific_total || 0} duration={1.2} /> 独有内容
                </span>
                <span>
                  <AnimatedNumber value={msg.result.summary.total_docs || 0} duration={1.2} /> 份文档
                </span>
              </div>
            )}
            <button
              className="w-full inline-flex items-center justify-center gap-2 font-medium text-sm transition-all duration-150 bg-success text-white hover:bg-emerald-600 shadow-sm h-12 px-6 rounded-[12px] cursor-pointer"
              onClick={() => {
                const a = document.createElement('a');
                a.href = msg.result.download_url;
                a.download = msg.result.filename || 'merged.docx';
                a.click();
              }}
            >
              <Download className="w-4 h-4" strokeWidth={1.5} />
              下载合并文档
            </button>
          </div>
        )}

        <div className={`text-[11px] mt-2 ${isUser ? 'text-white/60' : 'text-gray-400'}`}>
          {new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
        </div>
      </div>
    </motion.div>
  )
}
