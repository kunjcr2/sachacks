export type Workspace = 'patient' | 'doctor' | 'team'
export interface Claim { quote: string; location: string }
export interface Reason { criterion_id: string; status: string; reason?: string; patient_value?: string | number | boolean | null; patient_unit?: string | null; effective_date?: string | null; explanation: string }
export interface Study { id: string; title: string; version: number; pi: string; site: string; contact: string; status: string; risk: string; brief: { heading: string; text: string; source?: Claim | null }[]; source_url: string; label: string; importance?: Claim | null }
export interface Opportunity { listing_id: string; status: string; waiting_for_doctor: boolean; message?: string; study?: Study; reasons?: Reason[] }
export interface Recipient { pi: string; site: string; contact: string }
export interface Packet { name: string; preferred_contact: { method: string; value: string }; screening_summary: Reason[] }
export interface Introduction { id: string; listing_id: string; state: string; enrollment: string; recipient: Recipient; needs_reauthorization: boolean }
export interface Profile { patient: { id: string; assigned_pcp: string | null; record_version: number; deleted: boolean }; today: string; identity: { name: string; contact_method: string; contact: string } | null; permissions: Record<'screening' | 'records', { granted: boolean; version: number }>; credit: { label: string; amount: number; currency: string; state: string }; opportunities: Opportunity[]; introductions: Introduction[] }
export interface ClinicalFact { field: string; value: string | number | boolean; unit?: string | null; effective_date: string }
export interface ClinicalSummary { current: ClinicalFact[]; history: { version: number; effective_at: string; ingested_at: string; facts: ClinicalFact[] }[] }
export interface Discussion { id: string; patient_id: string; listing_id: string; outcome: string; note: string; identity: { name: string }; study: Study; reasons: Reason[]; at: string }
export interface Listing extends Study { study_id: string; owner: string; source: { kind: string; hash: string; eligibility: string; retrieved_at: string; documents: Record<string, string>; registry_sponsor?: string | null }; specification: { state: string; execution: string; model: string | null; errors: string[] }; receipt: { amount: number; currency: string; label: string } | null }
export interface TeamIntroduction { id: string; listing_id: string; state: string; enrollment: string; needs_reauthorization: boolean; approved_packet?: Packet; authorization: { study_version: number; record_version: number } }
export interface Preview { id: string; exact_packet: Packet; recipient: Recipient; purpose: string; study_version: number; record_version: number; expires_at: string }
