import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { useNavigate, useParams } from 'react-router'
import { toast } from 'sonner'
import { z } from 'zod'

import { ErrorState } from '@/components/common/ErrorState'
import { PageSkeleton } from '@/components/common/LoadingSpinner'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { AnimatedInput } from '@/components/ui/AnimatedInput'
import { GlassCard } from '@/components/ui/GlassCard'
import { GradientButton } from '@/components/ui/GradientButton'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useSaveTurf, useTurf } from '@/hooks/useTurfs'
import { formatTimeHHMM, humanize } from '@/lib/format'
import { nativeFieldClass, toastApiError } from '@/lib/toastError'
import { SPORT_TYPES, type SlotDurationMinutes, type SportType, type TurfCreate, type TurfRead } from '@/types'

const TIMEZONES = [
  'Asia/Kolkata',
  'Asia/Dubai',
  'Asia/Singapore',
  'Europe/London',
  'Europe/Berlin',
  'America/New_York',
  'America/Los_Angeles',
  'Australia/Sydney',
  'UTC',
]
const DURATIONS: SlotDurationMinutes[] = [30, 60, 90]
const HHMM = /^([01]\d|2[0-3]):[0-5]\d$/

const schema = z
  .object({
    name: z.string().trim().min(2, 'Name is required').max(120),
    description: z.string().max(2000),
    address: z.string().trim().min(3, 'Address is required').max(300),
    city: z.string().trim().min(2, 'City is required').max(80),
    timezone: z.string().min(1),
    sport_types: z.array(z.enum(SPORT_TYPES as [SportType, ...SportType[]])).min(1, 'Pick at least one sport'),
    amenities: z.string(),
    image_urls: z.string(),
    slot_duration_minutes: z.enum(['30', '60', '90']),
    opening_time: z.string().regex(HHMM, 'Use HH:MM'),
    closing_time: z.string().regex(HHMM, 'Use HH:MM'),
    base_price: z.string().refine((v) => Number(v) > 0, 'Enter a price greater than 0'),
    currency: z.string().trim().length(3, '3-letter code'),
  })
  .refine((v) => v.closing_time > v.opening_time, { path: ['closing_time'], message: 'Must be after opening time' })

type TurfFormValues = z.infer<typeof schema>

const EMPTY: TurfFormValues = {
  name: '',
  description: '',
  address: '',
  city: '',
  timezone: 'Asia/Kolkata',
  sport_types: [],
  amenities: '',
  image_urls: '',
  slot_duration_minutes: '60',
  opening_time: '06:00',
  closing_time: '23:00',
  base_price: '',
  currency: 'INR',
}

function toFormValues(t: TurfRead): TurfFormValues {
  return {
    name: t.name,
    description: t.description ?? '',
    address: t.address,
    city: t.city,
    timezone: t.timezone,
    sport_types: t.sport_types,
    amenities: t.amenities.join(', '),
    image_urls: t.image_urls.join('\n'),
    slot_duration_minutes: String(t.slot_duration_minutes) as TurfFormValues['slot_duration_minutes'],
    opening_time: formatTimeHHMM(t.opening_time),
    closing_time: formatTimeHHMM(t.closing_time),
    base_price: String(t.base_price / 100),
    currency: t.currency,
  }
}

function toPayload(v: TurfFormValues): TurfCreate {
  return {
    name: v.name.trim(),
    description: v.description.trim(),
    address: v.address.trim(),
    city: v.city.trim(),
    latitude: null,
    longitude: null,
    timezone: v.timezone,
    sport_types: v.sport_types,
    amenities: v.amenities
      .split(',')
      .map((a) => a.trim())
      .filter(Boolean),
    image_urls: v.image_urls
      .split('\n')
      .map((u) => u.trim())
      .filter(Boolean),
    slot_duration_minutes: Number(v.slot_duration_minutes) as SlotDurationMinutes,
    opening_time: v.opening_time,
    closing_time: v.closing_time,
    base_price: Math.round(Number(v.base_price) * 100),
    currency: v.currency.trim().toUpperCase(),
  }
}

export default function TurfFormPage() {
  const { id: idParam } = useParams()
  const id = idParam ? Number(idParam) : undefined
  const isEdit = id !== undefined
  const navigate = useNavigate()
  const turfQuery = useTurf(id)
  const save = useSaveTurf()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<TurfFormValues>({ resolver: zodResolver(schema), defaultValues: EMPTY })

  useEffect(() => {
    if (turfQuery.data) reset(toFormValues(turfQuery.data))
  }, [turfQuery.data, reset])

  if (isEdit && turfQuery.isLoading) return <PageSkeleton rows={6} />
  if (isEdit && turfQuery.isError) {
    return (
      <PageWrapper>
        <ErrorState error={turfQuery.error} onRetry={() => void turfQuery.refetch()} />
      </PageWrapper>
    )
  }

  const onSubmit = (values: TurfFormValues): void => {
    save.mutate(
      { id, body: toPayload(values) },
      {
        onSuccess: () => {
          toast.success(isEdit ? 'Turf updated' : 'Turf created')
          void navigate('/owner/turfs')
        },
        onError: (err) => toastApiError(err, 'Could not save turf'),
      },
    )
  }

  return (
    <PageWrapper title={isEdit ? 'Edit turf' : 'New turf'} className="max-w-3xl">
      <GlassCard hoverable={false}>
        <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} className="grid gap-4 sm:grid-cols-2" noValidate>
          <AnimatedInput label="Name" {...register('name')} error={errors.name?.message} />
          <AnimatedInput label="City" {...register('city')} error={errors.city?.message} />
          <AnimatedInput
            label="Address"
            containerClassName="sm:col-span-2"
            {...register('address')}
            error={errors.address?.message}
          />
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="description">Description</Label>
            <Textarea id="description" rows={3} {...register('description')} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="timezone">Timezone</Label>
            <select id="timezone" className={nativeFieldClass} {...register('timezone')}>
              {TIMEZONES.map((tz) => (
                <option key={tz} value={tz}>
                  {tz}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="slot_duration_minutes">Slot duration</Label>
            <select id="slot_duration_minutes" className={nativeFieldClass} {...register('slot_duration_minutes')}>
              {DURATIONS.map((d) => (
                <option key={d} value={String(d)}>
                  {d} minutes
                </option>
              ))}
            </select>
          </div>
          <AnimatedInput label="Opening time" type="time" {...register('opening_time')} error={errors.opening_time?.message} />
          <AnimatedInput label="Closing time" type="time" {...register('closing_time')} error={errors.closing_time?.message} />
          <AnimatedInput
            label="Base price per slot"
            type="number"
            min="0"
            step="0.01"
            hint="In major units (e.g. 1200 = ₹1,200)"
            {...register('base_price')}
            error={errors.base_price?.message}
          />
          <AnimatedInput label="Currency" maxLength={3} {...register('currency')} error={errors.currency?.message} />
          <fieldset className="space-y-2 sm:col-span-2">
            <legend className="text-sm font-medium">Sports</legend>
            <div className="flex flex-wrap gap-4">
              {SPORT_TYPES.map((s) => (
                <label key={s} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" value={s} className="size-4 accent-primary" {...register('sport_types')} />
                  {humanize(s)}
                </label>
              ))}
            </div>
            {errors.sport_types && <p className="text-sm text-destructive">{errors.sport_types.message}</p>}
          </fieldset>
          <AnimatedInput
            label="Amenities"
            containerClassName="sm:col-span-2"
            hint="Comma-separated, e.g. Parking, Floodlights, Washroom"
            {...register('amenities')}
          />
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="image_urls">Image URLs (one per line)</Label>
            <Textarea id="image_urls" rows={3} {...register('image_urls')} />
          </div>
          <div className="sm:col-span-2">
            <GradientButton type="submit" fullWidth loading={save.isPending} loadingText="Saving...">
              {isEdit ? 'Save changes' : 'Create turf'}
            </GradientButton>
          </div>
        </form>
      </GlassCard>
    </PageWrapper>
  )
}
