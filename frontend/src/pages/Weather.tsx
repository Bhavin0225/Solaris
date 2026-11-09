// Weather page (/weather). Sections are added by plan 07-06.
import { Clock } from 'lucide-react'
import { useSite, useTz, useWeather } from '../api'
import { PageHeader, Stagger } from '../components/ui'
import { makeFmt } from '../lib/time'

export default function Weather() {
  const name = useSite().data?.site.name
  const tz = useTz()
  const run = useWeather().data?.run_time

  return (
    <Stagger className="grid gap-6">
      <PageHeader
        title="Weather"
        subtitle={`Next 3 days${name ? ` in ${name}` : ''} · times in IST`}
        secondary={
          tz && run ? (
            <>
              <Clock size={16} strokeWidth={1.75} aria-hidden />
              Updated {makeFmt(tz).hour(Date.parse(run))} IST
            </>
          ) : undefined
        }
        primary={{ to: '/', label: 'See energy forecast' }}
      />
    </Stagger>
  )
}
