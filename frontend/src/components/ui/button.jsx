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
