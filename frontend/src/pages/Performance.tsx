// Performance page (/performance). Sections are added by plan 07-06.
import { PageHeader, Stagger } from '../components/ui'

export default function Performance() {
  return (
    <Stagger className="grid gap-6">
      <PageHeader
        title="Model performance"
        subtitle="Test year 2025, scored once. Skill = how much lower the RMSE is than baseline 3 (Open-Meteo + physics)."
        secondary="Test split · 2025"
        primary={{ to: '/about', label: 'Read the method' }}
      />
    </Stagger>
  )
}
