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
