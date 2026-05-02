import { useRef, useState, useCallback, useMemo, useEffect } from 'react'
import { Plus, ArrowUp, Loader2 } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

const SUGGESTIONS = [
  "合并这些文档",
  "合并成综合报告",
  "按时间顺序整理后合并",
]

export default function ChatInput({ onSend, onUpload, disabled, hasFiles }) {
  const [text, setText] = useState('')
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef(null)
  const textareaRef = useRef(null)

  const showSuggestions = useMemo(() => {
    return text.trim().length >= 1 && text.trim().length <= 6 && !disabled
  }, [text, disabled])

  // Auto-grow textarea
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 200) + 'px'
  }, [text])

  const handleSend = useCallback(() => {
    const trimmed = text.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setText('')
    // Reset height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
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
          return { filename: file.name, content: btoa(binary), size: file.size }
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

  const handleSuggestionClick = useCallback((suggestion) => {
    setText(suggestion)
    textareaRef.current?.focus()
  }, [])

  return (
    <div className="relative px-4 pb-3 pt-1 bg-transparent flex-shrink-0">
      <AnimatePresence>
        {showSuggestions && (
          <motion.div
            initial={{ opacity: 0, y: 4, height: 0 }}
            animate={{ opacity: 1, y: 0, height: 'auto' }}
            exit={{ opacity: 0, y: 4, height: 0 }}
            transition={{ type: 'spring', stiffness: 500, damping: 30 }}
            className="absolute bottom-full left-4 right-4 mb-2 bg-white border border-gray-200 rounded-xl shadow-lg overflow-hidden z-10 max-w-[740px] mx-auto"
          >
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => handleSuggestionClick(s)}
                className="w-full text-left px-4 py-2.5 text-[13px] text-gray-600 hover:bg-gray-50 hover:text-gray-900 transition-colors cursor-pointer border-b border-gray-50 last:border-0"
              >
                {s}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      <div className="max-w-[740px] mx-auto bg-white rounded-2xl border border-gray-200 shadow-lg overflow-hidden">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={hasFiles ? '描述你的合并需求，或直接说"合并"...' : '上传文档后，描述你的合并需求...'}
          rows={1}
          disabled={disabled}
          className="w-full border-0 outline-none bg-transparent text-[15px] leading-relaxed placeholder:text-gray-400 px-4 pt-3.5 pb-2 resize-none overflow-hidden disabled:opacity-60"
          style={{ minHeight: '56px' }}
        />

        <div className="flex items-center justify-between px-3 pb-3">
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled || uploading}
            className="w-8 h-8 rounded-lg hover:bg-gray-100 flex items-center justify-center cursor-pointer transition-colors flex-shrink-0 disabled:opacity-40"
            title="添加文档"
          >
            {uploading ? (
              <Loader2 className="w-[18px] h-[18px] animate-spin text-gray-400" strokeWidth={1.5} />
            ) : (
              <Plus className="w-[18px] h-[18px] text-gray-400" strokeWidth={1.5} />
            )}
          </button>

          <input
            ref={fileInputRef}
            type="file"
            accept=".docx"
            multiple
            onChange={handleFileChange}
            className="hidden"
          />

          <button
            onClick={handleSend}
            disabled={disabled || !text.trim()}
            className="w-8 h-8 rounded-lg bg-brand hover:bg-brand-hover flex items-center justify-center cursor-pointer transition-colors flex-shrink-0 disabled:opacity-40 disabled:bg-brand"
            title="发送"
          >
            <ArrowUp className="w-[18px] h-[18px] text-white" strokeWidth={2} />
          </button>
        </div>
      </div>

      {hasFiles && (
        <div className="text-center mt-2 text-[11px] text-gray-400">
          Enter 发送，Shift+Enter 换行
        </div>
      )}
    </div>
  )
}
