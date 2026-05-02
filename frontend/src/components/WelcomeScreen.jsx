import { motion } from "framer-motion"
import { Upload, GitMerge, Download, FileText, Sparkles } from "lucide-react"

const cards = [
  { icon: Upload, title: "上传文档", desc: "支持 .docx 格式", action: "上传" },
  { icon: GitMerge, title: "AI 智能合并", desc: "语义识别共性内容", action: "合并" },
  { icon: Download, title: "下载文档", desc: "一键保存结果", action: "下载" },
]

const presets = [
  "帮我合并这两份合同",
  "按时间顺序整理汇报材料",
  "分析文档差异并合并",
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

const tagVariants = {
  hidden: { opacity: 0, y: 4 },
  show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 500, damping: 30 } },
}

export default function WelcomeScreen({ onCardClick, onPromptClick }) {
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
        className="flex gap-3 max-w-[480px] w-full mb-6"
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

      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4, duration: 0.5 }}
        className="flex flex-wrap items-center justify-center gap-2 max-w-[420px]"
      >
        <Sparkles className="w-3.5 h-3.5 text-gray-300" strokeWidth={1.5} />
        {presets.map((text, i) => (
          <motion.button
            key={text}
            variants={tagVariants}
            initial="hidden"
            animate="show"
            transition={{ delay: 0.45 + i * 0.06 }}
            onClick={() => onPromptClick?.(text)}
            className="px-3.5 py-1.5 rounded-full border border-gray-200 bg-white/80 hover:bg-brand/5 hover:border-brand/30 text-[12px] text-gray-500 hover:text-brand transition-colors cursor-pointer"
          >
            {text}
          </motion.button>
        ))}
      </motion.div>
    </div>
  )
}
