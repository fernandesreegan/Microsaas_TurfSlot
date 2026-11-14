import { motion } from 'framer-motion'
import { useNavigate } from 'react-router'

import { PageWrapper } from '@/components/layout/PageWrapper'
import { GradientButton } from '@/components/ui/GradientButton'

export default function NotFoundPage() {
  const navigate = useNavigate()
  return (
    <PageWrapper title="Page not found" className="flex flex-1 flex-col items-center justify-center text-center">
      <motion.p
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 200, damping: 15 }}
        className="bg-linear-to-r from-brand-from to-brand-to bg-clip-text text-8xl font-black text-transparent"
      >
        404
      </motion.p>
      <p className="mt-4 text-muted-foreground">Looks like this ball went out of bounds.</p>
      <GradientButton className="mt-6" onClick={() => navigate('/')}>
        Back to home
      </GradientButton>
    </PageWrapper>
  )
}
