export interface User {
  id: string
  public_id: string
  email: string
  status: 'ACTIVE' | 'PENDING' | 'BLOCKED'
  mfa_enabled: boolean
  created_at: string
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
  created_at: string
}

export interface Professional {
  id: string
  user_id: string
  public_id: string
  full_name: string
  cpf_hash: string
  phone_encrypted?: string
  city: string
  state: string
  radius_km: number
  status: 'ACTIVE' | 'INACTIVE' | 'SUSPENDED'
  created_at: string
  email?: string
}
