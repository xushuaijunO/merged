import { forwardRef } from 'react'
import { cn } from "../../lib/utils"

const Textarea = forwardRef(({ className, ...props }, ref) => {
  return (
    <textarea
      ref={ref}
      className={cn(
        "flex min-h-[56px] w-full rounded-[10px] border border-gray-200 bg-white px-4 py-3.5 text-[15px] placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-brand/30 focus:border-brand transition-shadow resize-none",
        "disabled:bg-gray-50 disabled:opacity-60",
        className
      )}
      {...props}
    />
  )
})

Textarea.displayName = 'Textarea'
export default Textarea
