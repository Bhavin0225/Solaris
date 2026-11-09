// About page (/about). Cards are added by plan 07-07.
import { useSite } from '../api'
import { PageHeader, Stagger } from '../components/ui'

export default function About() {
  const name = useSite().data?.site.name
  return (
    <Stagger className="grid gap-6">
      <PageHeader
        title="About this project"
        subtitle={`Bhavin's final-year project: 72-hour solar, wind and weather forecasts${name ? ` for ${name}` : ''}.`}
        primary={{ to: '/performance', label: 'See model accuracy' }}
      />
    </Stagger>
  )
}
