import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export default function Welcome() {
  const nav = useNavigate()
  const { access } = useAuth()
  const go = () => nav('/start')
  const rise = (d: number) => ({
    initial: { opacity: 0, y: 24 },
    animate: { opacity: 1, y: 0 },
    transition: { delay: d, duration: 0.6, ease: [0.22, 1, 0.36, 1] as const },
  })
  return (
    <main className="welcome">
      <motion.h1
        className="mark"
        initial={{ opacity: 0, scale: 0.94 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
      >
        RØVE
      </motion.h1>
      <motion.p className="tag" {...rise(0.25)}>The aux, handled.</motion.p>
      <motion.p className="cta-line" {...rise(0.4)}>Plug in. Pick the vibe. Party.</motion.p>
      <motion.button className="btn btn-primary btn-next enter" onClick={go} {...rise(0.55)}>
        Enter RØVE →
      </motion.button>
      <motion.p className="fine" {...rise(0.7)}>
        Tell RØVE the room and it builds the set.
        {access === 'member' && <> <button onClick={() => nav('/sets')}>My sets</button></>}
      </motion.p>
    </main>
  )
}