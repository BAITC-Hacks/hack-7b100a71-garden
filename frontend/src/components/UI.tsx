import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Link } from 'react-router'
import { copy } from '../i18n/en'
import { Icon } from './Icon'

export function Button({ className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className={`button ${className}`} type="button" {...props} />
}

export function StatePanel({ title, description, children, error = false }: { title: string; description: string; children?: ReactNode; error?: boolean }) {
  return <section className="state-panel surface" role={error ? 'alert' : undefined}>
    <span className="state-icon"><Icon name="compass" /></span>
    <h2>{title}</h2><p>{description}</p>{children}
  </section>
}

export function LoadingPanel({ label = copy.loadingTitle }: { label?: string }) {
  return <section className="surface loading-panel" role="status" aria-live="polite" aria-busy="true">
    <div className="skeleton skeleton-heading" /><div className="skeleton skeleton-line" />
    <div className="skeleton-grid">{[0, 1, 2].map((key) => <div className="skeleton skeleton-card" key={key} />)}</div>
    <span className="sr-only">{label}. {copy.loadingDescription}</span>
  </section>
}

export function BackLink() {
  return <Link className="text-link back-link" to="/"><Icon name="arrow" />{copy.back}</Link>
}

export function Avatar({ name, large = false }: { name: string; large?: boolean }) {
  const initials = name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join('')
  return <span className={`avatar ${large ? 'avatar-large' : ''}`} aria-hidden="true">{initials}</span>
}
