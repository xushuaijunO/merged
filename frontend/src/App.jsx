import { useState, useEffect, useCallback, useRef } from 'react'
import ChatWindow from './components/ChatWindow'
import ChatInput from './components/ChatInput'
import HistorySidebar from './components/HistorySidebar'
import Badge from './components/ui/badge'
import { Menu } from 'lucide-react'

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
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const saveToHistoryRef = useRef(null)

  useEffect(() => {
    fetch(`${API_BASE}/chat/start`, { method: 'POST' })
      .then(r => r.json())
      .then(data => setSessionId(data.session_id))
      .catch(err => console.error('Failed to create session:', err))
  }, [])

  const addMessage = useCallback((msg) => {
    setMessages(prev => [...prev, msg])
  }, [])

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
      addMessage({ role: 'user', content: `上传了 ${data.added} 个文档`, files: fileData.map(f => ({ filename: f.filename, size: f.size })) })
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
    // Finalize any stale streaming messages from previous interrupted merges
    setMessages(prev => prev.map(m => m._streaming ? { ...m, _streaming: false } : m))
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
                  streamedContent += data.text
                  upsertAgentMsg({ content: streamedContent, progress: streamedProgress })
                  break

                case 'tool_call': {
                  const toolName = data.tool || ''
                  const label = TOOL_LABELS[toolName] || toolName
                  setMessages(prev => {
                    const copy = [...prev]
                    const last = copy[copy.length - 1]
                    if (last && last.role === 'agent' && last._streaming) {
                      last.toolCall = { name: toolName, label }
                    } else {
                      copy.push({ role: 'agent', _streaming: true, content: '', toolCall: { name: toolName, label } })
                    }
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
                  // Reset content — subsequent message events from Claude's
                  // text response will append to this same result message
                  streamedContent = ''
                  streamedProgress = null
                  if (saveToHistoryRef.current) {
                    saveToHistoryRef.current({
                      title: data.filename?.replace(/\.docx$/i, '') || '文档合并',
                      fileCount: data.summary?.total_docs || uploadedFiles.length,
                      filenames: [...uploadedFiles],
                    })
                  }
                  // Push a streaming result message — Claude's follow-up text
                  // will land here via upsertAgentMsg because _streaming is true
                  setMessages(prev => [...prev, { role: 'agent', _streaming: true, content: '', result: data }])
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
        }
        return copy
      })
    } catch (err) {
      addMessage({ role: 'agent', content: `❌ 处理失败：${err.message}` })
    } finally {
      setIsProcessing(false)
    }
  }, [sessionId, isProcessing, addMessage])

  const handleQuickAction = useCallback((action) => {
    if (action === '上传') {
      document.querySelector('input[type="file"]')?.click()
    } else if (action === '合并') {
      handleSend('合并这些文档')
    } else if (action === '下载') {
      const lastResult = [...messages].reverse().find(m => m.result?.download_url)
      if (lastResult) {
        const a = document.createElement('a')
        a.href = lastResult.result.download_url
        a.download = lastResult.result.filename || 'merged.docx'
        a.click()
      }
    }
  }, [messages, handleSend])

  const handlePromptClick = useCallback((text) => {
    handleSend(text)
  }, [handleSend])

  const handleRemoveFile = useCallback((filename) => {
    setUploadedFiles(prev => prev.filter(f => f !== filename))
  }, [])

  return (
    <div className="min-h-screen bg-app-pattern flex items-start justify-center py-4">
    <HistorySidebar
      onSaveRef={saveToHistoryRef}
      sidebarOpen={sidebarOpen}
      onToggle={() => setSidebarOpen(false)}
    />
    <div className="h-screen flex flex-col max-w-[740px] w-full mx-auto bg-white shadow-[0_0_0_1px_rgba(0,0,0,0.04),0_1px_3px_rgba(0,0,0,0.06)] rounded-2xl overflow-hidden">
      <header className="flex items-center gap-3 h-[52px] px-5 border-b border-gray-100 flex-shrink-0 bg-white">
        <button
          onClick={() => setSidebarOpen(v => !v)}
          className="w-8 h-8 rounded-lg hover:bg-gray-100 flex items-center justify-center cursor-pointer transition-colors -ml-1"
        >
          <Menu className="w-4 h-4 text-gray-400" strokeWidth={1.5} />
        </button>
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
        onPromptClick={handlePromptClick}
        onRemoveFile={handleRemoveFile}
      />

      <ChatInput
        onSend={handleSend}
        onUpload={handleUpload}
        disabled={isProcessing || !sessionId}
        hasFiles={uploadedFiles.length > 0}
      />
    </div>
    </div>
  )
}
