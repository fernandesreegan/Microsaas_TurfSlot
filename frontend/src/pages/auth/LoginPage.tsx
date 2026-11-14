import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { toast } from 'sonner'
import { z } from 'zod'

import { GoogleSignInButton } from '@/components/auth/GoogleSignInButton'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { AnimatedInput } from '@/components/ui/AnimatedInput'
import { GlassCard } from '@/components/ui/GlassCard'
import { GradientButton } from '@/components/ui/GradientButton'
import { useAuth } from '@/hooks/useAuth'
import { homePathForRole, safeNextPath } from '@/lib/roles'
import { getApiError } from '@/services/api'

const schema = z.object({
  email: z.email('Enter a valid email'),
  password: z.string().min(1, 'Password is required'),
})

type LoginValues = z.infer<typeof schema>

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({ resolver: zodResolver(schema), defaultValues: { email: '', password: '' } })

  const onSubmit = async (values: LoginValues): Promise<void> => {
    try {
      const user = await login(values.email, values.password)
      toast.success(`Welcome back, ${user.full_name}`)
      void navigate(safeNextPath(params.get('next')) ?? homePathForRole(user.role), { replace: true })
    } catch (err: unknown) {
      toast.error('Login failed', { description: getApiError(err).detail })
    }
  }

  return (
    <PageWrapper title="Log in" className="max-w-md">
      <GlassCard hoverable={false}>
        <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} className="space-y-4" noValidate>
          <AnimatedInput label="Email" type="email" autoComplete="email" {...register('email')} error={errors.email?.message} />
          <AnimatedInput
            label="Password"
            type="password"
            autoComplete="current-password"
            {...register('password')}
            error={errors.password?.message}
          />
          <GradientButton type="submit" fullWidth loading={isSubmitting} loadingText="Logging in...">
            Log in
          </GradientButton>
        </form>
        <div className="mt-4">
          <GoogleSignInButton />
        </div>
        <div className="mt-4 flex justify-between text-sm">
          <Link to="/forgot-password" className="text-primary hover:underline">
            Forgot password?
          </Link>
          <Link to="/register" className="text-primary hover:underline">
            Create an account
          </Link>
        </div>
      </GlassCard>
    </PageWrapper>
  )
}
