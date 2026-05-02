import { useEffect, useState } from 'react'
import { animate, useMotionValue, useTransform } from 'framer-motion'

export default function AnimatedNumber({ value = 0, duration = 1.5, className }) {
  const count = useMotionValue(0)
  const rounded = useTransform(count, v => Math.round(v))
  const [display, setDisplay] = useState(0)

  useEffect(() => {
    const unsubscribe = rounded.on('change', setDisplay)
    return () => unsubscribe()
  }, [rounded])

  useEffect(() => {
    const controls = animate(count, value, { duration, ease: 'easeOut' })
    return () => controls.stop()
  }, [value, duration, count])

  return <span className={className}>{display}</span>
}
