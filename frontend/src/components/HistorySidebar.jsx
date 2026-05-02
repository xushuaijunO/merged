import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Clock, FileText, PanelLeftClose, PanelLeft, ChevronRight } from 'lucide-react'
import useLocalStorage from '../hooks/useLocalStorage'

export default function HistorySidebar({ onSaveRef, sidebarOpen, onToggle }) {
  const [history] = useLocalStorage('merge-history', [])

  if (typeof onSaveRef === 'object' && onSaveRef !== null) {
    onSaveRef.current = (entry) => {
      const stored = JSON.parse(localStorage.getItem('merge-history') || '[]')
      const updated = [
        {
          id: Date.now(),
          timestamp: new Date().toISOString(),
          ...entry,
        },
        ...stored,
      ].slice(0, 20)
      localStorage.setItem('merge-history', JSON.stringify(updated))
    }
  }

  return (
    <>
      <AnimatePresence>
        {sidebarOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/10 z-30 lg:hidden"
            onClick={onToggle}
          />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {sidebarOpen && (
          <motion.div
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 260, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 400, damping: 35 }}
            className="fixed left-0 top-0 bottom-0 z-40 bg-white border-r border-gray-100 shadow-lg overflow-hidden"
          >
            <div className="flex flex-col h-full" style={{ width: 260 }}>
              <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
                <span className="text-[14px] font-semibold text-gray-800">历史记录</span>
                <button
                  onClick={onToggle}
                  className="w-7 h-7 rounded-lg hover:bg-gray-100 flex items-center justify-center cursor-pointer transition-colors"
                >
                  <PanelLeftClose className="w-4 h-4 text-gray-400" strokeWidth={1.5} />
                </button>
              </div>

              <div className="flex-1 overflow-y-auto">
                {history.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
                    <Clock className="w-8 h-8 text-gray-200 mb-3" strokeWidth={1.5} />
                    <p className="text-[13px] text-gray-400">暂无历史记录</p>
                    <p className="text-[11px] text-gray-300 mt-1">完成合并后会自动保存</p>
                  </div>
                ) : (
                  history.map((entry) => (
                    <div
                      key={entry.id}
                      className="px-4 py-3 border-b border-gray-50 hover:bg-gray-50/60 transition-colors cursor-pointer"
                    >
                      <div className="flex items-start gap-3">
                        <div className="w-8 h-8 rounded-lg bg-brand/6 flex items-center justify-center flex-shrink-0 mt-0.5">
                          <FileText className="w-4 h-4 text-brand" strokeWidth={1.5} />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-[13px] font-medium text-gray-800 truncate">
                            {entry.title || '文档合并'}
                          </p>
                          <p className="text-[11px] text-gray-400 mt-0.5">
                            {entry.fileCount} 份文档
                          </p>
                          <p className="text-[11px] text-gray-300 mt-0.5">
                            {new Date(entry.timestamp).toLocaleDateString('zh-CN', {
                              month: 'short',
                              day: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </p>
                        </div>
                        <ChevronRight className="w-4 h-4 text-gray-300 flex-shrink-0 mt-1" strokeWidth={1.5} />
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
