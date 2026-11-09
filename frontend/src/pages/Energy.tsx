// Energy page (/). Sections are added by plan 07-05.
import { Clock } from 'lucide-react'
import { useState } from 'react'
import { useForecast, useSite, useTz } from '../api'
import { PageHeader, Stagger } from '../components/ui'
import { greeting, istParts, makeFmt } from '../lib/time'

export default function Energy() {
  const name = useSite().data?.site.name
  const tz = useTz()
  const run = useForecast().data?.run_time
  const [now] = useState(() => Date.now()) // greeting fixed per page visit
  const fmt = tz ? makeFmt(tz) : null

  return (
    <Stagger className="grid gap-6">
      <PageHeader
        title={tz && name ? `${greeting(istParts(now, tz).hour)}, ${name}` : 'Energy forecast'}
        subtitle={`${fmt ? `${fmt.longDate(now)} · ` : ''}72-hour forecast, refreshed every hour`}
        secondary={
          fmt && run ? (
            <>
              <Clock size={16} strokeWidth={1.75} aria-hidden />
              Updated {fmt.hour(Date.parse(run))} IST
            </>
          ) : undefined
        }
        primary={{ to: '/performance', label: 'See model accuracy' }}
      />
    </Stagger>
  )
}
