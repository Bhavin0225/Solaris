import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useEffect } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Shell } from './components/Shell'
import About from './pages/About'
import Energy from './pages/Energy'
import Performance from './pages/Performance'
import Weather from './pages/Weather'

export default function App() {
  const location = useLocation()
  const reduce = useReducedMotion()

  useEffect(() => {
    if (!location.hash) window.scrollTo(0, 0)
  }, [location.pathname, location.hash])

  return (
    <Shell>
      {/* The frosted panel stays put; only its content blurs out and back in. */}
      <AnimatePresence mode="wait">
        <motion.div
          key={location.pathname}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1, filter: 'blur(0px)', transition: { duration: 0.12 } }}
          exit={
            reduce
              ? { opacity: 0, transition: { duration: 0.12 } }
              : { opacity: 0, filter: 'blur(12px)', transition: { duration: 0.18, ease: [0.4, 0, 1, 1] } }
          }
        >
          <Routes location={location}>
            <Route path="/" element={<Energy />} />
            <Route path="/weather" element={<Weather />} />
            <Route path="/performance" element={<Performance />} />
            <Route path="/about" element={<About />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </motion.div>
      </AnimatePresence>
    </Shell>
  )
}
