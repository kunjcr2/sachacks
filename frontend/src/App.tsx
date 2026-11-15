import { useCallback, useEffect, useState } from 'react'
import { Activity, ArrowRight, ArrowUpRight, BookOpen, Check, CheckCircle2, ChevronDown, CircleHelp, ClipboardCheck, ClipboardList, FileHeart, FlaskConical, HeartHandshake, LayoutDashboard, LoaderCircle, Menu, Plus, ShieldCheck, Stethoscope, Users, X } from 'lucide-react'
import { api } from './api'
import { date, FeedbackContext, initials, Modal } from './components'
import Patient from './Patient'
import Doctor from './Doctor'
import Team from './Team'
import type { ClinicalSummary, Discussion, Listing, Profile, TeamIntroduction, Workspace } from './types'

const baseAccounts = [{ id: 'patient-1', name: 'Alex Demo', detail: 'Assigned usual doctor' }, { id: 'patient-2', name: 'Sam Example', detail: 'No assigned doctor' }]
export default function App() {
  const [actor, setActor] = useState('')
  const [profile, setProfile] = useState<Profile | null>(null)
  const [clinical, setClinical] = useState<ClinicalSummary>({ current: [], history: [] })
  const [queue, setQueue] = useState<Discussion[]>([])
  const [listings, setListings] = useState<Listing[]>([])
  const [introductions, setIntroductions] = useState<TeamIntroduction[]>([])
  const [page, setPage] = useState('overview')
  const [lastPatient, setLastPatient] = useState(() => sessionStorage.getItem('rematch_patient') || 'patient-1')
  const [lastTeam, setLastTeam] = useState('team-1')
  const [customPatients, setCustomPatients] = useState<string[]>(() => { try { return JSON.parse(sessionStorage.getItem('rematch_created_patients') || '[]') } catch { return [] } })
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [refresh, setRefresh] = useState(0)
  const [guide, setGuide] = useState(false)
  const [accountOpen, setAccountOpen] = useState(false)
  const [mobileNav, setMobileNav] = useState(false)
  const [newProfile, setNewProfile] = useState(false)
  const [name, setName] = useState('Taylor Synthetic')
  const [contact, setContact] = useState('taylor@example.invalid')
  const [assigned, setAssigned] = useState(true)
  const workspace: Workspace = actor.startsWith('doctor-') ? 'doctor' : actor.startsWith('team-') ? 'team' : 'patient'
  const reload = useCallback(() => setRefresh(n => n + 1), [])
  const navigate = (next: string) => { setPage(next); setMobileNav(false); window.scrollTo({ top: 0, behavior: 'smooth' }) }

  useEffect(() => {
    let active = true
    api<{ actor: string }>('/demo/session').catch(() => api<{ actor: string }>('/demo/session', 'POST', { actor: 'patient-1' })).then(result => {
      if (active) { setActor(result.actor); setPage(result.actor.startsWith('doctor-') ? 'review' : result.actor.startsWith('team-') ? 'listings' : 'overview'); if (result.actor.startsWith('patient-')) { setLastPatient(result.actor); sessionStorage.setItem('rematch_patient', result.actor) } }
    }).catch(err => { if (active) { setError(err.message); setLoading(false) } })
    return () => { active = false }
  }, [])
  useEffect(() => {
    if (!actor) return
    let active = true
    const load = async () => {
      if (actor.startsWith('patient-')) {
        const [p, c] = await Promise.all([api<Profile>('/me'), api<ClinicalSummary>('/me/clinical-summary')])
        if (active) { setProfile(p); setClinical(c) }
      } else if (actor.startsWith('doctor-')) {
        const q = await api<Discussion[]>('/doctor/discussions')
        if (active) setQueue(q)
      } else if (actor.startsWith('team-')) {
        const [l, i] = await Promise.all([api<Listing[]>('/team/listings'), api<TeamIntroduction[]>('/team/introductions')])
        if (active) { setListings(l); setIntroductions(i) }
      }
    }
    load().catch(err => { if (active) setError(err.message) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [actor, refresh])
  useEffect(() => { if (notice) { const timeout = window.setTimeout(() => setNotice(''), 6500); return () => window.clearTimeout(timeout) } }, [notice])
  const run = async (task: () => Promise<unknown>, message?: string) => {
    if (busy) return false
    setBusy(true); setError('')
    try { await task(); if (message) setNotice(message); reload(); return true }
    catch (err) { setError(err instanceof Error ? err.message : 'Something went wrong. Try again.'); return false }
    finally { setBusy(false) }
  }
  const chooseActor = async (next: string, nextPage?: string) => {
    setAccountOpen(false)
    if (next === actor) { if (nextPage) navigate(nextPage); return }
    setBusy(true); setError('')
    try {
      await api('/demo/session', 'POST', { actor: next })
      if (next.startsWith('patient-')) { setLastPatient(next); sessionStorage.setItem('rematch_patient', next) }
      if (next.startsWith('team-')) setLastTeam(next)
      setLoading(true); setActor(next); setProfile(null); setPage(nextPage || (next.startsWith('doctor-') ? 'review' : next.startsWith('team-') ? 'listings' : 'overview'))
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to switch demo account.') }
    finally { setBusy(false) }
  }
  const accounts = [...baseAccounts, ...customPatients.map(id => ({ id, name: 'My new profile', detail: 'Created in this browser session' }))]
  const displayName = workspace === 'patient' ? (profile?.identity?.name || accounts.find(a => a.id === actor)?.name || 'Patient account') : workspace === 'doctor' ? 'Your usual doctor' : actor === 'team-1' ? 'Demo Research Center' : 'Second Demo Site'
  const navItems = workspace === 'patient' ? [{ id: 'overview', label: 'Overview', icon: LayoutDashboard }, { id: 'studies', label: 'My studies', icon: FlaskConical }, { id: 'introductions', label: 'Introductions', icon: HeartHandshake }, { id: 'records', label: 'Records & privacy', icon: FileHeart }] : workspace === 'doctor' ? [{ id: 'review', label: 'Discussion queue', icon: ClipboardCheck }] : [{ id: 'listings', label: 'Study listings', icon: ClipboardList }, { id: 'team-introductions', label: 'Introductions', icon: HeartHandshake }]
  const createProfile = async (event: React.FormEvent) => {
    event.preventDefault()
    if (busy) return
    setBusy(true); setError('')
    try {
      await api('/demo/session', 'POST', { actor: 'onboarding' })
      const result = await api<{ patient_id: string }>('/profiles', 'POST', { name, contact_method: 'email', contact, assigned_pcp: assigned ? 'doctor-1' : null })
      const ids = [...customPatients, result.patient_id]
      setCustomPatients(ids); sessionStorage.setItem('rematch_created_patients', JSON.stringify(ids)); sessionStorage.setItem('rematch_patient', result.patient_id)
      setLastPatient(result.patient_id); setLoading(true); setActor(result.patient_id); setProfile(null); setPage('overview'); setNewProfile(false); setNotice('Profile created. Your time credit is earned; matching permission remains optional.'); reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Profile could not be created.')
      try { await api('/demo/session', 'POST', { actor: lastPatient }) } catch { /* Keep the visible error available for retry. */ }
    } finally { setBusy(false) }
  }
  return <FeedbackContext.Provider value={error}><div className="app-shell">
    <aside className={'sidebar ' + (mobileNav ? 'sidebar-open' : '')}><a className="brand" href="#" onClick={e => { e.preventDefault(); navigate(workspace === 'patient' ? 'overview' : workspace === 'doctor' ? 'review' : 'listings') }}><span className="brand-mark"><Activity size={23} strokeWidth={1.8} /></span>re<span className="brand-match">match</span><span className="brand-period">.</span></a><div className="sidebar-context"><span className="eyebrow">A LITTLE MORE POSSIBILITY</span><p>Research, on your terms.</p></div><nav aria-label="Main navigation">{navItems.map(item => <button key={item.id} className={'nav-item ' + (page === item.id ? 'nav-active' : '')} onClick={() => navigate(item.id)}><item.icon size={18} strokeWidth={1.6} />{item.label}{item.id === 'introductions' && !!profile?.introductions.length && <span className="nav-count">{profile.introductions.length}</span>}</button>)}</nav><div className="sidebar-bottom"><div className="sidebar-help"><span className="help-monogram"><BookOpen size={20} strokeWidth={1.4} /></span><h3>A clear path through the demo.</h3><p>One patient. A record change. A choice about research.</p><button className="text-button" onClick={() => setGuide(true)}>Open demo guide <ArrowUpRight size={15} /></button></div><div className="sidebar-safety"><ShieldCheck size={15} /><span>Synthetic patients.<br />Real choices, simulated here.</span></div></div><button className="mobile-close icon-button" aria-label="Close navigation" onClick={() => setMobileNav(false)}><X size={19} /></button></aside>
    {mobileNav && <button className="mobile-shade" aria-label="Close navigation" onClick={() => setMobileNav(false)} />}
    <div className="main-shell"><header className="topbar"><div className="topbar-left"><button className="mobile-menu icon-button" aria-label="Open navigation" onClick={() => setMobileNav(true)}><Menu size={21} /></button><span className="topbar-breadcrumb">Workspace <span>/</span> <strong>{workspace === 'patient' ? 'My studies' : workspace === 'doctor' ? 'Doctor review' : 'Study team'}</strong></span></div><div className="workspace-switch" aria-label="Demo workspace">{[{ id: 'patient', label: 'Patient', icon: Users }, { id: 'doctor', label: 'Doctor', icon: Stethoscope }, { id: 'team', label: 'Research team', icon: FlaskConical }].map(item => <button key={item.id} disabled={busy} className={workspace === item.id ? 'workspace-active' : ''} onClick={() => chooseActor(item.id === 'patient' ? lastPatient : item.id === 'doctor' ? 'doctor-1' : lastTeam)}><item.icon size={14} />{item.label}</button>)}</div><div className="account-wrap"><button className="account-button" aria-label="Switch demo account" aria-expanded={accountOpen} onClick={() => setAccountOpen(!accountOpen)}><span className="avatar">{initials(displayName)}</span><span className="account-label"><strong>{displayName}</strong><small>Demo account</small></span><ChevronDown size={14} /></button>{accountOpen && <><button className="account-dismiss" aria-label="Close account menu" onClick={() => setAccountOpen(false)} /><div className="account-menu"><div className="eyebrow">SWITCH DEMO ACCOUNT</div>{(workspace === 'patient' ? accounts.map(a => ({ id: a.id, name: a.name, detail: a.detail })) : workspace === 'doctor' ? [{ id: 'doctor-1', name: 'Assigned usual doctor', detail: 'Focused discussion access' }] : [{ id: 'team-1', name: 'Demo Research Center', detail: 'Research team one' }, { id: 'team-2', name: 'Second Demo Site', detail: 'Research team two' }]).map(a => <button key={a.id} onClick={() => chooseActor(a.id)}><div><strong>{a.name}</strong><span>{a.detail}</span></div>{actor === a.id && <Check size={16} />}</button>)}{workspace === 'patient' && <button className="new-account" onClick={() => { setAccountOpen(false); setNewProfile(true) }}><Plus size={16} /> Create a profile</button>}<p>Role switching is a local simulation, not production login.</p></div></>}</div></header>
    <div className="demo-ribbon"><span className="demo-label">DEMO</span><span>Type 2 diabetes research <span className="ribbon-dot">·</span> Synthetic records, permissions and introductions</span><button onClick={() => setGuide(true)}>How this works <CircleHelp size={13} /></button></div>
    <main id="main-content" className="main-content"><div className="content-date"><span><span className="live-dot" /> LOCAL RESEARCH WORKSPACE</span><span>{profile ? date(profile.today) : 'Synthetic research prototype'}</span></div>
      {error && <div className="alert alert-error" role="alert"><span>{error}</span><button className="icon-button" aria-label="Dismiss error" onClick={() => setError('')}><X size={16} /></button></div>}
      {loading ? <div className="loading-state" role="status"><LoaderCircle size={23} className="spin" /><p>Opening your workspace…</p></div> : <>
        {workspace === 'patient' && profile && <Patient key={actor} profile={profile} clinical={clinical} page={page} navigate={navigate} run={run} busy={busy} reload={reload} />}
        {workspace === 'doctor' && <Doctor queue={queue} run={run} busy={busy} />}
        {workspace === 'team' && <Team listings={listings} introductions={introductions} page={page} run={run} busy={busy} />}
        {!actor && <button className="button button-dark" onClick={() => chooseActor('patient-1')}>Open demo workspace <ArrowRight size={16} /></button>}
      </>}
      <footer className="page-footer"><span>ReMatch <span className="footer-cross">/</span> A patient-first research screening prototype.</span><span>No real messages, charges or medical decisions.</span></footer>
    </main></div>
    {notice && <div className="toast" role="status"><CheckCircle2 size={19} /><span>{notice}</span><button className="icon-button" aria-label="Dismiss notification" onClick={() => setNotice('')}><X size={15} /></button></div>}
    {busy && <div className="request-indicator" role="status"><LoaderCircle size={14} className="spin" /> Saving your choice…</div>}
    {guide && <Modal title="One patient. A clearer research path." eyebrow="THE REMATCH DEMO" onClose={() => setGuide(false)}><p className="modal-intro">Follow Alex’s synthetic diabetes research journey. The change in the record is the reason to reassess—not the passage of time.</p><ol className="guide-steps"><li><span>01</span><div><h3>Connect once, with permission.</h3><p>In the patient workspace, grant matching and simulated record-access permissions. Connect the local fixture.</p></div></li><li><span>02</span><div><h3>See what fits today.</h3><p>Alex’s HbA1c starts at 11.2%. The fictional ReNew study requires 7.5–10%. That lab requirement is not met yet.</p></div></li><li><span>03</span><div><h3>Change a record. See a rematch.</h3><p>Under Records & privacy → Demo controls, load the 9.1% follow-up. The lab requirement now passes; the research team still decides formal eligibility.</p></div></li><li><span>04</span><div><h3>Bring the doctor in when needed.</h3><p>Low-risk opportunities appear directly. Higher or unknown-risk opportunities need a discussion recorded in the doctor workspace.</p></div></li><li><span>05</span><div><h3>The patient makes the introduction.</h3><p>Preview the exact name, contact and screening summary. Authorize one named team. Switch to Research team to see only that approved packet.</p></div></li></ol><div className="notice"><strong>Safeguards:</strong> no PHI in model prompts; no team candidate browsing; exact preview before each share; encrypted records; separate matching, record, discussion, and introduction permissions.</div><div className="notice">Every patient, record, payment, introduction and outcome here is simulated. No real Epic account is connected.</div><button className="button button-dark button-full" onClick={() => setGuide(false)}>Back to the workspace <ArrowRight size={17} /></button></Modal>}
    {newProfile && <Modal title="Start with a profile. Keep your choices." eyebrow="PATIENT ONBOARDING" onClose={() => setNewProfile(false)}><p className="modal-intro">No clinic invitation is needed. Use fictional information only. Matching and record access remain optional after onboarding.</p><form onSubmit={createProfile}><label className="field-label" htmlFor="profile-name">Synthetic name</label><input id="profile-name" value={name} onChange={e => setName(e.target.value)} required maxLength={100} /><label className="field-label" htmlFor="profile-contact">Synthetic email</label><input id="profile-contact" type="email" value={contact} onChange={e => setContact(e.target.value)} required maxLength={150} /><label className="checkbox-label"><input type="checkbox" checked={assigned} onChange={e => setAssigned(e.target.checked)} /><span>Assign the demo usual doctor for discussions.</span></label><p className="fine-print">The modest simulated credit is earned for onboarding time. Declining matching or enrollment does not forfeit it.</p><button className="button button-dark button-full" type="submit" disabled={busy}>Create my synthetic profile <ArrowRight size={17} /></button></form></Modal>}
  </div></FeedbackContext.Provider>
}
