import { Construction } from 'lucide-react'

import { EmptyState } from '@/components/common/EmptyState'
import { PageWrapper } from '@/components/layout/PageWrapper'

export interface ComingSoonProps {
  title: string
  description?: string
}

/** Phase-1 placeholder used by every page until Phase 2 replaces it. */
export function ComingSoon({ title, description }: ComingSoonProps) {
  return (
    <PageWrapper title={title} description={description}>
      <EmptyState
        icon={Construction}
        title="Coming soon"
        description="This page is under construction and will be available shortly."
      />
    </PageWrapper>
  )
}
