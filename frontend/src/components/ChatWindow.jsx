import { useEffect, useRef } from "react"
import { motion } from "framer-motion"
import ChatMessage from "./ChatMessage"
import WelcomeScreen from "./WelcomeScreen"

export default function ChatWindow({ messages, isProcessing, onQuickAction, onPromptClick, onRemoveFile }) {
  const containerRef = useRef(null)
  const bottomRef = useRef(null)
  const userScrolledUp = useRef(false)

  const handleScroll = () => {
    const el = containerRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60
    userScrolledUp.current = !atBottom
  }

  useEffect(() => {
    if (!userScrolledUp.current) {
      requestAnimationFrame(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
      })
    }
  }, [messages, isProcessing])

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-4 chat-window"
    >
      {messages.length === 0 ? (
        <WelcomeScreen onCardClick={onQuickAction} onPromptClick={onPromptClick} />
      ) : (
        messages.map((msg, idx) => (
          <ChatMessage key={idx} msg={msg} onRemoveFile={onRemoveFile} />
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
