import { motion, type Variants } from 'framer-motion'

import { cn } from '@/lib/utils'

const container: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.06 } },
}

const word: Variants = {
  hidden: { opacity: 0, y: '0.5em' },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: 'easeOut' } },
}

export interface TextRevealProps {
  text: string
  as?: 'h1' | 'h2' | 'h3' | 'p'
  className?: string
  /** Classes applied to each word (e.g. gradient text). */
  wordClassName?: string
}

/** Headline that reveals word by word. */
export function TextReveal({ text, as = 'h1', className, wordClassName }: TextRevealProps) {
  const Tag = motion[as]
  return (
    <Tag initial="hidden" animate="visible" variants={container} className={className} aria-label={text}>
      {text.split(' ').map((w, i) => (
        <motion.span
          key={`${w}-${i}`}
          variants={word}
          aria-hidden="true"
          className={cn('mr-[0.25em] inline-block last:mr-0', wordClassName)}
        >
          {w}
        </motion.span>
      ))}
    </Tag>
  )
}
