import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router'
import { toast } from 'sonner'
import { z } from 'zod'

import { GoogleSignInButton } from '@/components/auth/GoogleSignInButton'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { AnimatedInput } from '@/components/ui/AnimatedInput'
import { GlassCard } from '@/components/ui/GlassCard'
import { GradientButton } from '@/components/ui/GradientButton'
import { useAuth } from '@/hooks/useAuth'
import { cn } from '@/lib/utils'
import { getApiError } from '@/services/api'

const schema = z.object({
  full_name: z.string().trim().min(1, 'Name is required').max(120),
  email: z.email('Enter a valid email'),
  phone: z.string().trim().max(20).optional(),
  password: z
    .string()
    .min(8, 'At least 8 characters')
    .regex(/[A-Za-z]/, 'Must contain a letter')
    .regex(/\d/, 'Must contain a digit'),
})

type RegisterValues = z.infer<typeof schema>
type Role = 'player' | 'owner'

export default function RegisterPage() {
  const { register: registerUser } = useAuth()
  const [role, setRole] = useState<Role>('player')
  const [registeredEmail, setRegisteredEmail] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterValues>({
    resolver: zodResolver(schema),
    defaultValues: { full_name: '', email: '', phone: '', password: '' },
  })

  const onSubmit = async (values: RegisterValues): Promise<void> => {
    try {
      await registerUser({ ...values, phone: values.phone || undefined, role })
      setRegisteredEmail(values.email)
    } catch (err: unknown) {
      toast.error('Registration failed', { description: getApiError(err).detail })
    }
  }

  if (registeredEmail) {
    return (
      <PageWrapper title="Check your inbox" className="max-w-md">
        <GlassCard hoverable={false} className="space-y-4 text-center">
          <p>
            We sent a verification link to <span className="font-semibold">{registeredEmail}</span>. Verify your email,
            then log in.
          </p>
          <Link to="/login" className="font-medium text-primary hover:underline">
            Go to login
          </Link>
        </GlassCard>
      </PageWrapper>
    )
  }

  return (
    <PageWrapper title="Create account" className="max-w-md">
      <GlassCard hoverable={false}>
        <div className="mb-4 grid grid-cols-2 gap-2 rounded-full bg-muted p-1" role="radiogroup" aria-label="Account type">
          {(['player', 'owner'] as const).map((r) => (
            <button
              key={r}
              type="button"
              role="radio"
              aria-checked={role === r}
              onClick={() => setRole(r)}
              className={cn(
                'rounded-full py-2 text-sm font-medium transition-colors',
                role === r ? 'bg-background shadow' : 'text-muted-foreground',
              )}
            >
              {r === 'player' ? 'I want to play' : 'I own a turf'}
            </button>
          ))}
        </div>
        <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} className="space-y-4" noValidate>
          <AnimatedInput label="Full name" autoComplete="name" {...register('full_name')} error={errors.full_name?.message} />
          <AnimatedInput label="Email" type="email" autoComplete="email" {...register('email')} error={errors.email?.message} />
          <AnimatedInput label="Phone (optional)" type="tel" autoComplete="tel" {...register('phone')} error={errors.phone?.message} />
          <AnimatedInput
            label="Password"
            type="password"
            autoComplete="new-password"
            hint="Min 8 characters with a letter and a digit"
            {...register('password')}
            error={errors.password?.message}
          />
          <GradientButton type="submit" fullWidth loading={isSubmitting} loadingText="Creating account...">
            Sign up as {role}
          </GradientButton>
        </form>
        <div className="mt-4">
          <GoogleSignInButton role={role} />
        </div>
        <p className="mt-4 text-center text-sm">
          Already have an account?{' '}
          <Link to="/login" className="text-primary hover:underline">
            Log in
          </Link>
        </p>
      </GlassCard>
    </PageWrapper>
  )
}
