export interface MembershipInfo {
  id: string
  organization_id: string
  organization_name?: string
  role_id: string
  role_name: string
  status: string
}

export type JourneyType = 'LOCATIONS' | 'PROFESSIONALS'
export type JourneyStatus = 'PENDING' | 'ACTIVE' | 'SUSPENDED' | 'INACTIVE' | 'REJECTED'
export type ParticipantBankAccountStatus =
  | 'PENDING'
  | 'VERIFIED'
  | 'REJECTED'
  | 'INACTIVE'

export interface BankAccount {
  id: string
  bank_code: string
  bank_name: string
  branch: string
  account_number_masked: string
  account_type: string
  holder_name: string
  holder_cpf_masked?: string
  pix_key_type?: string
  pix_key_masked?: string
  status: ParticipantBankAccountStatus
  is_primary: boolean
  verified_at?: string
  rejection_reason?: string
  created_at?: string
  updated_at?: string
}

export interface BankAccountPayload {
  bank_code: string
  bank_name: string
  branch: string
  account_number: string
  account_type: string
  holder_name: string
  holder_cpf?: string
  pix_key_type?: string
  pix_key?: string
  is_primary?: boolean
}

export interface FamilyMember {
  id: string
  full_name: string
  kinship: string
  birth_date?: string
  phone_masked?: string
  cpf_masked?: string
  is_legal_guardian: boolean
  authorization_reference?: string
  notes?: string
  created_at?: string
  updated_at?: string
}

export interface FamilyMemberPayload {
  full_name: string
  kinship: string
  birth_date?: string
  phone?: string
  cpf?: string
  is_legal_guardian?: boolean
  authorization_reference?: string
  notes?: string
}

export type InvitationPurpose =
  | 'GLOBAL_REGISTRATION'
  | 'PROFESSIONAL_NETWORK'
  | 'LOCATION_REPRESENTATIVE'
  | 'MISSION_PARTICIPANT'
export type ParticipantDataCategory =
  | 'PROFILE'
  | 'CONTACT'
  | 'ADDRESS'
  | 'BANK'
  | 'FAMILY'
  | 'DOCUMENTS'
  | 'QUALIFICATIONS'

export interface Journey {
  id: string
  journey_type: JourneyType
  status: JourneyStatus
  activated_at?: string
  requirements_met_at?: string
  created_at?: string
}

export interface Qualification {
  id: string
  user_id: string
  function_name: string
  status: 'PENDING' | 'ACTIVE' | 'SUSPENDED' | 'EXPIRED' | 'REVOKED'
  certification_id?: string
  course_version_id?: string
  issued_at: string
  expires_at?: string
  suspended_reason?: string
}

export interface PersonProfileUpdatePayload {
  full_name?: string
  social_name?: string
  birth_date?: string
  gender?: string
  phone?: string
  rg?: string
  city?: string
  state?: string
  zip_code?: string
  address_street?: string
  address_number?: string
  address_complement?: string
  address_neighborhood?: string
  emergency_contact_name?: string
  emergency_contact_phone?: string
  bio?: string
}

export interface PersonProfile {
  user_id: string
  public_id: string
  email: string
  full_name: string
  social_name?: string
  cpf_masked: string
  phone_masked: string
  rg_masked?: string
  birth_date?: string
  gender?: string
  city: string
  state: string
  zip_code?: string
  address_street?: string
  address_number?: string
  address_complement?: string
  address_neighborhood?: string
  emergency_contact_name?: string
  emergency_contact_phone_masked?: string
  bio?: string
  has_avatar: boolean
  avatar_url?: string
  profile_completed: boolean
  created_at?: string
  updated_at?: string
}

export interface Account {
  profile: PersonProfile
  journeys: Journey[]
  qualifications: Qualification[]
}

export type ParticipantValidationStatus =
  | 'PENDING'
  | 'VALIDATED'
  | 'REJECTED'
  | 'SUSPENDED'
  | 'UPDATE_REQUIRED'
export type ParticipantValidationScope =
  | 'GLOBAL'
  | 'PROFILE'
  | 'DOCUMENTS'
  | 'BANK'
  | 'FAMILY'
  | 'QUALIFICATIONS'

export interface ParticipantLinkedOrganization {
  organization_id: string
  organization_name?: string
  purpose: string
  status: string
  valid_from?: string
}

export interface ParticipantSummary {
  user_id: string
  public_id: string
  full_name: string
  city: string
  state: string
  cadastral_status: ParticipantValidationStatus
  profile_completed: boolean
  has_avatar: boolean
  avatar_url?: string
  journeys: Journey[]
  qualifications: Qualification[]
  created_at?: string
}

export interface ParticipantDetail extends ParticipantSummary {
  social_name?: string
  cpf_masked: string
  phone_masked: string
  birth_date?: string
  gender?: string
  organizations: ParticipantLinkedOrganization[]
}

export interface ParticipantValidation {
  id: string
  user_id: string
  scope: ParticipantValidationScope
  status: ParticipantValidationStatus
  reviewer_user_id?: string
  reviewer_public_id?: string
  organization_id?: string
  notes?: string
  created_at?: string
}

export interface ParticipantValidationPayload {
  scope: ParticipantValidationScope
  status: ParticipantValidationStatus
  notes?: string
  organization_id?: string
}

export interface User {
  id: string
  public_id: string
  email: string
  status: 'ACTIVE' | 'PENDING' | 'BLOCKED'
  mfa_enabled: boolean
  created_at: string
  primary_role?: 'ADMIN' | 'CLIENT' | 'PARTICIPANT' | 'USER'
  roles?: string[]
  memberships?: MembershipInfo[]
  professional?: Professional
  journeys?: Journey[]
  qualifications?: Qualification[]
}

export interface Organization {
  id: string
  public_id: string
  name: string
  status: 'ACTIVE' | 'INACTIVE' | 'SUSPENDED'
  created_at: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: User
}


export interface Lesson {
  id: string
  module_id: string
  title: string
  content_type: 'VIDEO' | 'PDF' | 'TEXT'
  content?: string
  duration_minutes: number
  order_index: number
}

export interface Module {
  id: string
  course_version_id: string
  title: string
  order_index: number
  lessons: Lesson[]
}

export interface CourseVersion {
  id: string
  course_id: string
  version_tag: string
  is_active: boolean
  created_at: string
  modules: Module[]
}

export interface Course {
  id: string
  organization_id?: string
  title: string
  description?: string
  thumbnail_url?: string
  status: 'DRAFT' | 'PUBLISHED' | 'ARCHIVED'
  audience: 'GLOBAL' | 'LOCATIONS' | 'PROFESSIONALS'
  created_at: string
  versions: CourseVersion[]
}

export interface Certification {
  id: string
  user_id: string
  course_version_id: string
  status: 'VALID' | 'EXPIRED' | 'REVOKED'
  score?: number
  issued_at: string
  expires_at?: string
  course_title?: string
  version_tag?: string
}

export interface Location {
  id: string
  organization_id?: string
  name: string
  address: string
  city: string
  state: string
  neighborhood?: string
  zip_code?: string
  latitude?: number
  longitude?: number
  total_rooms: number
  total_capacity: number
  has_accessibility: boolean
  has_air_conditioning: boolean
  status: 'DECLARADO' | 'VISTORIADO' | 'CONFIRMADO'
  reliability_score: number
  created_at: string
}

export interface Mission {
  id: string
  title: string
  mission_type: 'CAPTACAO' | 'VISTORIA' | 'RECERTIFICACAO' | 'CONFIRMACAO' | 'APOIO_OPERACIONAL'
  status: 'OPEN' | 'ASSIGNED' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED'
  location_id?: string
  location_name?: string
  assigned_user_id?: string
  city: string
  state: string
  reward_amount: number
  deadline?: string
  checklist?: { item: string; done: boolean }[]
  required_function?: string
  created_at: string
}

export type ApplicationStatus = 'APPLIED' | 'WITHDRAWN' | 'SELECTED' | 'REJECTED'

export interface MissionApplication {
  id: string
  mission_id: string
  user_id: string
  public_id?: string
  full_name?: string
  status: ApplicationStatus
  applied_at: string
  decided_at?: string
  notes?: string
}

export type MissionInvitationStatus = 'INVITED' | 'ACCEPTED' | 'DECLINED' | 'CANCELLED'

export interface MissionInvitation {
  id: string
  mission_id: string
  user_id: string
  public_id?: string
  full_name?: string
  function_name?: string
  status: MissionInvitationStatus
  message?: string
  mission_title?: string
  mission_status?: string
  mission_city?: string
  mission_state?: string
  location_name?: string
  reward_amount?: number
  created_at?: string
  responded_at?: string
}

export interface Invitation {
  id: string
  email: string
  journey_type: JourneyType
  purpose: InvitationPurpose
  mission_id?: string
  required_data_categories: ParticipantDataCategory[]
  organization_id?: string
  organization_name?: string
  location_id?: string
  location_name?: string
  status: 'PENDING' | 'ACCEPTED' | 'REVOKED' | 'EXPIRED'
  token_prefix?: string
  token?: string
  accept_path?: string
  expires_at: string
  accepted_at?: string
  revoked_at?: string
  created_at?: string
}

export type PublicInvitationStatus = 'ACTIVE' | 'REVOKED' | 'EXPIRED'

export interface PublicInvitation {
  id: string
  label?: string
  journey_type: JourneyType
  purpose: InvitationPurpose
  mission_id?: string
  required_data_categories: ParticipantDataCategory[]
  organization_id?: string
  organization_name?: string
  location_id?: string
  location_name?: string
  status: PublicInvitationStatus
  expires_at: string
  max_uses?: number
  uses_count: number
  accept_path?: string
  token?: string
  revoked_at?: string
  created_at?: string
}

export interface PublicInvitationValidation {
  valid: boolean
  status: PublicInvitationStatus
  label?: string
  journey_type: JourneyType
  purpose: InvitationPurpose
  mission_id?: string
  required_data_categories: ParticipantDataCategory[]
  organization_id?: string
  organization_name?: string
  location_id?: string
  location_name?: string
  expires_at: string
  max_uses?: number
  uses_count: number
  requires_account: boolean
}

export interface InvitationValidation {
  valid: boolean
  status: Invitation['status']
  email: string
  journey_type: JourneyType
  purpose: InvitationPurpose
  mission_id?: string
  required_data_categories: ParticipantDataCategory[]
  organization_id?: string
  organization_name?: string
  location_id?: string
  location_name?: string
  expires_at: string
  requires_account: boolean
}

export type RegistrationDraftStatus = 'IN_PROGRESS' | 'SUBMITTED' | 'EXPIRED'

export interface RegistrationDraft {
  status: RegistrationDraftStatus
  current_step: number
  data: Record<string, unknown>
  expires_at: string
  updated_at?: string
}

export interface RepresentativeLink {
  id: string
  location_id: string
  location_name?: string
  city?: string
  state?: string
  status: 'INVITED' | 'ACTIVE' | 'SUSPENDED' | 'ENDED'
  responsibilities?: unknown
  started_at?: string
}

export interface WorkflowEvent {
  id: string
  location_id: string
  stage: 'CAPTURE' | 'DOCUMENTATION' | 'INSPECTION' | 'RELEASE'
  status: 'PENDING' | 'SUBMITTED' | 'APPROVED' | 'REJECTED'
  actor_user_id?: string
  notes?: string
  created_at?: string
}

export interface DocumentItem {
  id: string
  owner_type: 'PERSON' | 'LOCATION' | 'REPRESENTATIVE_LINK'
  owner_id: string
  document_type: string
  file_name: string
  mime_type: string
  size_bytes: number
  sha256: string
  status: 'PENDING' | 'APPROVED' | 'REJECTED'
  rejection_reason?: string
  expires_at?: string
  reviewed_at?: string
  created_at?: string
  download_path: string
}

export interface Professional {
  id: string
  user_id: string
  public_id?: string
  full_name: string
  cpf_hash?: string
  phone_encrypted?: string
  city: string
  state: string
  operational_radius_km?: number
  radius_km?: number
  reputation_score?: number
  availability_status?: 'AVAILABLE' | 'UNAVAILABLE' | 'IN_MISSION'
  status?: 'ACTIVE' | 'INACTIVE' | 'SUSPENDED'
  qualifications?: string[]
  created_at?: string
  email?: string
}

