import { useState, useCallback } from 'react'

export default function useLocalStorage(key, initialValue) {
  const [value, setValue] = useState(() => {
    try {
      const stored = localStorage.getItem(key)
      return stored !== null ? JSON.parse(stored) : initialValue
    } catch {
      return initialValue
    }
  })

  const setAndPersist = useCallback((newValue) => {
    setValue(prev => {
      const resolved = typeof newValue === 'function' ? newValue(prev) : newValue
      try {
        localStorage.setItem(key, JSON.stringify(resolved))
      } catch { /* quota exceeded or private browsing */ }
      return resolved
    })
  }, [key])

  return [value, setAndPersist]
}
