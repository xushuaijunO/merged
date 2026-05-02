import { useState, createContext, useContext } from "react"
import { cn } from "../../lib/utils"

const CollapsibleContext = createContext({ open: false, toggle: () => {} })

export function Collapsible({ defaultOpen = false, open: controlledOpen, onOpenChange, children, className }) {
  const [internalOpen, setInternalOpen] = useState(defaultOpen)
  const isControlled = controlledOpen !== undefined
  const open = isControlled ? controlledOpen : internalOpen

  const toggle = () => {
    if (isControlled) {
      onOpenChange?.(!open)
    } else {
      setInternalOpen(v => !v)
    }
  }

  return (
    <CollapsibleContext.Provider value={{ open, toggle }}>
      <div className={cn("rounded-[12px] border border-gray-100 overflow-hidden", className)}>
        {children}
      </div>
    </CollapsibleContext.Provider>
  )
}

export function CollapsibleTrigger({ children, className }) {
  const { toggle } = useContext(CollapsibleContext)
  return (
    <div onClick={toggle} className={cn("cursor-pointer select-none", className)}>
      {children}
    </div>
  )
}

export function CollapsibleContent({ children, className }) {
  const { open } = useContext(CollapsibleContext)
  if (!open) return null
  return <div className={cn("border-t border-gray-100", className)}>{children}</div>
}
