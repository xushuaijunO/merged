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
