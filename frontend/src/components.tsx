import { createContext, useContext, useEffect, useRef, type ReactNode } from 'react'
import { ArrowUpRight, Check, CheckCircle2, ChevronRight, FileText, Info, ShieldCheck, X } from 'lucide-react'
import type { Reason, Study } from './types'

export const FeedbackContext = createContext('')

export const date = (value?: string) => value ? new Date(value.slice(0, 10) + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : 'Not available'
export const initials = (name = '') => name.split(' ').map(s => s[0]).slice(0, 2).join('')
export const fieldName = (key: string) => ({ age: 'Age', hba1c: 'HbA1c', egfr: 'Kidney function (eGFR)', bmi: 'Body mass index' }[key] || key.replaceAll('_', ' '))
export const stateName = (value: string) => ({ SHARED: 'Introduction sent', ACKNOWLEDGED: 'Research team acknowledged', NEED_INFO: 'More information requested', SCREENING_INVITED: 'Invited to formal screening', CLOSED: 'Closed', WITHDRAWN: 'Withdrawn', NOT_REPORTED: 'Enrollment not reported', SIMULATED_ENROLLED: 'Simulated enrollment recorded', PENDING: 'Discussion needed', COMPLETED: 'Discussion completed', DEFERRED: 'Deferred for now' }[value] || value.toLowerCase().replaceAll('_', ' '))

export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: string }) {
  return <span className={'badge badge-' + tone}><span className="badge-dot" />{children}</span>
}
export function Empty({ icon = <FileText size={24} />, title, children, action }: { icon?: ReactNode; title: string; children: ReactNode; action?: ReactNode }) {
  return <div className="empty-state"><span className="empty-icon">{icon}</span><h3>{title}</h3><p>{children}</p>{action}</div>
}
export function Modal({ title, eyebrow, children, onClose, wide = false }: { title: string; eyebrow?: string; children: ReactNode; onClose: () => void; wide?: boolean }) {
  const error = useContext(FeedbackContext)
  const ref = useRef<HTMLDialogElement>(null)
  const savedClose = useRef(onClose)
  savedClose.current = onClose
  useEffect(() => {
    const dialog = ref.current!
    dialog.showModal()
    document.body.style.overflow = 'hidden'
    const cancel = (event: Event) => { event.preventDefault(); savedClose.current() }
    dialog.addEventListener('cancel', cancel)
    return () => { document.body.style.overflow = ''; dialog.removeEventListener('cancel', cancel); dialog.close() }
  }, [])
  return <dialog ref={ref} className={'modal ' + (wide ? 'modal-wide' : '')} onClick={e => { if (e.target === e.currentTarget) onClose() }}>
    <div className="modal-header"><div>{eyebrow && <div className="eyebrow">{eyebrow}</div>}<h2>{title}</h2></div><button className="icon-button" aria-label="Close dialog" onClick={onClose}><X size={20} /></button></div>
    <div className="modal-body">{error && <div className="alert alert-error" role="alert">{error}</div>}{children}</div>
  </dialog>
}
export function Brief({ study }: { study: Study }) {
  return <><div className="brief">{study.brief.map((line, i) => <section key={line.heading}><span className="brief-number">{String(i + 1).padStart(2, '0')}</span><div><h4>{line.heading}</h4><p>{line.text}</p></div></section>)}</div>
    {study.importance && <div className="research-note"><Info size={16} /><p>{study.importance.quote}</p></div>}
    <p className="fine-print">{study.label}. Automated demo validation; formal eligibility is determined by the research team.</p>
    {study.source_url?.startsWith('https://') && <a className="text-button" href={study.source_url} target="_blank" rel="noreferrer">Read the original study source <ArrowUpRight size={15} /></a>}
  </>
}
export function Reasons({ reasons }: { reasons: Reason[] }) {
  return <div className="reasons">{reasons.map(reason => <div className="reason" key={reason.criterion_id}>
    {reason.status === 'MET' ? <CheckCircle2 size={17} className="green" /> : <Info size={17} className={reason.status === 'NOT_MET' ? 'rust' : 'muted'} />}
    <div><strong>{fieldName(reason.criterion_id)}</strong><span>{reason.explanation}</span></div>
    {reason.patient_value !== null && reason.patient_value !== undefined && <span className="reason-value">{String(reason.patient_value)} {reason.patient_unit}</span>}
  </div>)}</div>
}
export function PrivacyNote({ children }: { children: ReactNode }) {
  return <div className="privacy-note"><ShieldCheck size={17} /><span>{children}</span></div>
}
export function Step({ number, title, done = false, children }: { number: number; title: string; done?: boolean; children: ReactNode }) {
  return <div className={'setup-step ' + (done ? 'step-done' : '')}><span className="step-number">{done ? <Check size={16} /> : number}</span><div><h3>{title}</h3>{children}</div><ChevronRight size={16} className="step-chevron" /></div>
}
