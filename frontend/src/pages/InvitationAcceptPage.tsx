import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Building2,
  CheckCircle2,
  FileText,
  Mail,
  ShieldCheck,
  Trash2,
  Upload,
  Users,
  Camera,
} from 'lucide-react'
import api from '../api/client'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { useAuth } from '../hooks/useAuth'
import { homePathForUser } from '../lib/authRoutes'
import { getApiErrorMessage } from '../lib/errors'
import type {
  Account,
  AuthResponse,
  BankAccountPayload,
  FamilyMemberPayload,
  InvitationValidation,
  PublicInvitationValidation,
  RegistrationDraft,
} from '../types'

const initialState = {
  email: '',
  password: '',
  full_name: '',
  social_name: '',
  cpf: '',
  phone: '',
  rg: '',
  birth_date: '',
  gender: '',
  city: '',
  state: '',
  zip_code: '',
  address_street: '',
  address_number: '',
  address_complement: '',
  address_neighborhood: '',
  emergency_contact_name: '',
  emergency_contact_phone: '',
  bio: '',
}

const initialBank = {
  bank_code: '',
  bank_name: '',
  branch: '',
  account_number: '',
  account_type: 'CHECKING',
  holder_name: '',
  holder_cpf: '',
  pix_key_type: '',
  pix_key: '',
  is_primary: true,
}

const initialFamily = {
  full_name: '',
  kinship: '',
  birth_date: '',
  phone: '',
  cpf: '',
  is_legal_guardian: false,
  authorization_reference: '',
  notes: '',
}

const CATEGORY_LABELS: Record<string, string> = {
  PROFILE: 'Perfil',
  CONTACT: 'Contato',
  ADDRESS: 'Endereco',
  BANK: 'Dados bancarios',
  FAMILY: 'Familia',
  DOCUMENTS: 'Documentos',
  QUALIFICATIONS: 'Qualificacoes',
}

const STEPS = [
  { title: 'Perfil', hint: 'Dados pessoais e foto' },
  { title: 'Endereco', hint: 'Localizacao e contato' },
  { title: 'Complementares', hint: 'Banco e familia' },
  { title: 'Finalizacao', hint: 'Documentos e consentimento' },
]

const DOCUMENT_TYPES = [
  'RG',
  'CNH',
  'CPF',
  'PROOF_OF_ADDRESS',
  'EDUCATION',
  'HEALTH',
  'CRIMINAL_RECORD',
  'OTHER',
]

type PendingDocument = {
  type: string
  file: File
}

const MAX_AVATAR_SOURCE_BYTES = 25 * 1024 * 1024
const MAX_AVATAR_BYTES = 5 * 1024 * 1024
const MAX_DOCUMENT_BYTES = 10 * 1024 * 1024

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(new Error('Falha ao ler arquivo.'))
    reader.readAsDataURL(file)
  })
}

function compressImage(file: File, maxDimension: number, quality = 0.85): Promise<File> {
  return new Promise((resolve, reject) => {
    const objectUrl = URL.createObjectURL(file)
    const image = new Image()
    image.onload = () => {
      try {
        const scale = Math.min(1, maxDimension / Math.max(image.width, image.height))
        const canvas = document.createElement('canvas')
        canvas.width = Math.max(1, Math.round(image.width * scale))
        canvas.height = Math.max(1, Math.round(image.height * scale))
        const context = canvas.getContext('2d')
        if (!context) throw new Error('Canvas indisponivel.')
        context.drawImage(image, 0, 0, canvas.width, canvas.height)
        canvas.toBlob(
          (blob) => {
            URL.revokeObjectURL(objectUrl)
            if (!blob) {
              reject(new Error('Falha ao processar imagem.'))
              return
            }
            const baseName = file.name.replace(/\.[^./\\]+$/, '') || 'foto'
            resolve(
              new File([blob], `${baseName}.jpg`, {
                type: 'image/jpeg',
                lastModified: Date.now(),
              })
            )
          },
          'image/jpeg',
          quality
        )
      } catch (error) {
        URL.revokeObjectURL(objectUrl)
        reject(error)
      }
    }
    image.onerror = () => {
      URL.revokeObjectURL(objectUrl)
      reject(new Error('Nao foi possivel ler a imagem.'))
    }
    image.src = objectUrl
  })
}

export function InvitationAcceptPage() {
  const { token = '' } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const isPublicLink = location.pathname.startsWith('/convite-publico')
  const { user, loading: authLoading } = useAuth()
  const [form, setForm] = useState(initialState)
  const [documents, setDocuments] = useState<PendingDocument[]>([])
  const [documentType, setDocumentType] = useState('RG')
  const [documentProcessing, setDocumentProcessing] = useState(false)
  const [error, setError] = useState('')
  const [warning, setWarning] = useState('')
  const [avatarBase64, setAvatarBase64] = useState('')
  const [avatarMimeType, setAvatarMimeType] = useState('')
  const [avatarPreview, setAvatarPreview] = useState('')
  const [avatarProcessing, setAvatarProcessing] = useState(false)
  const [consent, setConsent] = useState(false)
  const [step, setStep] = useState(1)
  const [bank, setBank] = useState(initialBank)
  const [family, setFamily] = useState(initialFamily)
  const [draftSavedAt, setDraftSavedAt] = useState('')
  const [draftMessage, setDraftMessage] = useState('')
  const draftApplied = useRef(false)
  const documentCameraRef = useRef<HTMLInputElement>(null)
  const documentUploadRef = useRef<HTMLInputElement>(null)
  const avatarCameraRef = useRef<HTMLInputElement>(null)
  const avatarUploadRef = useRef<HTMLInputElement>(null)

  const account = useQuery({
    queryKey: ['account-me'],
    queryFn: () => api.get<Account>('/account/me').then((r) => r.data),
    enabled: Boolean(user),
    retry: false,
  })

  useEffect(() => {
    const profile = account.data?.profile
    if (!profile) return
    setForm((current) => ({
      ...current,
      full_name: profile.full_name || '',
      social_name: profile.social_name || '',
      cpf: '',
      rg: profile.rg_masked || '',
      birth_date: profile.birth_date || '',
      gender: profile.gender || '',
      city: profile.city || '',
      state: profile.state || '',
      zip_code: profile.zip_code || '',
      address_street: profile.address_street || '',
      address_number: profile.address_number || '',
      address_complement: profile.address_complement || '',
      address_neighborhood: profile.address_neighborhood || '',
      emergency_contact_name: profile.emergency_contact_name || '',
      bio: profile.bio || '',
    }))
  }, [account.data])

  useEffect(() => {
    if (!isPublicLink || !user?.email) return
    setForm((current) =>
      current.email ? current : { ...current, email: user.email || '' }
    )
  }, [isPublicLink, user])

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [step])

  const validation = useQuery({
    queryKey: [isPublicLink ? 'public-invitation-validation' : 'invitation-validation', token],
    queryFn: () =>
      api
        .get<InvitationValidation | PublicInvitationValidation>(
          isPublicLink
            ? `/invitations/public/validate/${token}`
            : `/invitations/validate/${token}`
        )
        .then((r) => r.data),
    enabled: Boolean(token),
    retry: false,
  })

  const draft = useQuery({
    queryKey: ['registration-draft', isPublicLink, token],
    queryFn: () =>
      api
        .get<RegistrationDraft>(
          isPublicLink
            ? `/invitations/public/${token}/draft`
            : `/invitations/${token}/draft`
        )
        .then((r) => r.data)
        .catch((err) => {
          if (err?.response?.status === 404) return null
          throw err
        }),
    enabled: Boolean(token) && Boolean(validation.data?.valid),
    retry: false,
  })

  useEffect(() => {
    if (!draft.data?.data || draftApplied.current) return
    const saved = draft.data.data
    setForm((current) => {
      const next = { ...current }
      for (const field of Object.keys(initialState) as (keyof typeof initialState)[]) {
        const value = saved[field]
        if (typeof value === 'string') next[field] = value
      }
      return next
    })
    const savedBank = saved.bank
    if (savedBank && typeof savedBank === 'object' && !Array.isArray(savedBank)) {
      setBank((current) => ({ ...current, ...(savedBank as typeof initialBank) }))
    }
    const savedFamily = saved.family
    if (savedFamily && typeof savedFamily === 'object' && !Array.isArray(savedFamily)) {
      setFamily((current) => ({ ...current, ...(savedFamily as typeof initialFamily) }))
    }
    const savedStep = Number(draft.data.current_step)
    if (savedStep >= 1 && savedStep <= STEPS.length) {
      setStep(savedStep)
    }
    setDraftSavedAt(
      draft.data.updated_at
        ? new Date(draft.data.updated_at).toLocaleString('pt-BR')
        : 'rascunho anterior'
    )
    draftApplied.current = true
  }, [draft.data])

  const requiredCategories = validation.data?.required_data_categories ?? []
  const needsBank = requiredCategories.includes('BANK')
  const needsFamily = requiredCategories.includes('FAMILY')
  const needsDocuments = requiredCategories.includes('DOCUMENTS')
  const hasBankData = Boolean(
    bank.bank_code ||
      bank.bank_name ||
      bank.branch ||
      bank.account_number ||
      bank.holder_name ||
      bank.pix_key
  )
  const hasFamilyData = Boolean(
    family.full_name ||
      family.kinship ||
      family.phone ||
      family.cpf
  )
  const bankReady = Boolean(
    bank.bank_code &&
      bank.bank_name &&
      bank.branch &&
      bank.account_number &&
      (bank.holder_name || form.full_name)
  )
  const familyReady = Boolean(family.full_name && family.kinship)

  const goNext = () => {
    setError('')
    setWarning('')
    if (step === 1) {
      if (isPublicLink && !form.email.trim()) {
        setError('Informe seu e-mail para continuar.')
        return
      }
      if (!form.full_name.trim()) {
        setError('Informe seu nome completo.')
        return
      }
      if (needsPassword && form.password.length < 8) {
        setError('Crie uma senha com ao menos 8 caracteres.')
        return
      }
      if (creatingAccount && !form.cpf.trim()) {
        setError('Informe seu CPF.')
        return
      }
      if (creatingAccount && !form.birth_date) {
        setError('Informe sua data de nascimento.')
        return
      }
      if (creatingAccount && !form.phone.trim()) {
        setError('Informe seu telefone.')
        return
      }
      if (avatarProcessing) {
        setError('Aguarde o processamento da foto de perfil.')
        return
      }
      if (avatarMissing) {
        setError('A foto de perfil e obrigatoria.')
        return
      }
    }
    if (step === 2 && (!form.city.trim() || !form.state.trim())) {
      setError('Informe cidade e estado.')
      return
    }
    if (step === 3 && needsBank && !bankReady) {
      setError('Preencha os dados bancarios solicitados neste convite.')
      return
    }
    if (step === 3 && needsFamily && !familyReady) {
      setError('Informe ao menos nome e parentesco do familiar solicitado.')
      return
    }
    if (step >= STEPS.length) return
    setStep((current) => Math.min(current + 1, STEPS.length))
    saveDraft.mutate(Math.min(step + 1, STEPS.length))
  }

  const goBack = () => {
    setError('')
    setWarning('')
    setStep((current) => Math.max(1, current - 1))
  }

  const saveDraft = useMutation({
    mutationFn: (stepToSave?: number) => {
      const { password: _password, ...draftData } = form
      return api
        .put<RegistrationDraft>(
          isPublicLink
            ? `/invitations/public/${token}/draft`
            : `/invitations/${token}/draft`,
          { current_step: stepToSave ?? step, data: { ...draftData, bank, family } }
        )
        .then((r) => r.data)
    },
    onSuccess: (data) => {
      setDraftSavedAt(
        data.updated_at
          ? new Date(data.updated_at).toLocaleString('pt-BR')
          : new Date().toLocaleString('pt-BR')
      )
      setDraftMessage('Rascunho salvo. Voce pode continuar depois pelo mesmo link.')
      setError('')
    },
    onError: (err) =>
      setError(getApiErrorMessage(err, 'Nao foi possivel salvar o rascunho.')),
  })

  const accept = useMutation({
    mutationFn: async () => {
      const response = await api
        .post<AuthResponse>(
          isPublicLink
            ? `/invitations/public/${token}/accept`
            : `/invitations/${token}/accept`,
          {
          ...form,
          email: form.email || undefined,
          birth_date: form.birth_date || undefined,
          password: form.password || undefined,
          social_name: form.social_name || undefined,
          full_name: form.full_name || undefined,
          cpf: form.cpf || undefined,
          phone: form.phone || undefined,
          rg: form.rg || undefined,
          gender: form.gender || undefined,
          city: form.city || undefined,
          state: form.state || undefined,
          zip_code: form.zip_code || undefined,
          address_street: form.address_street || undefined,
          address_number: form.address_number || undefined,
          address_complement: form.address_complement || undefined,
          address_neighborhood: form.address_neighborhood || undefined,
          emergency_contact_name: form.emergency_contact_name || undefined,
          emergency_contact_phone: form.emergency_contact_phone || undefined,
          bio: form.bio || undefined,
          avatar_base64: avatarBase64 || undefined,
          avatar_mime_type: avatarMimeType || undefined,
          privacy_consent: consent,
          consent_version: '2026-01',
          }
        )
        .then((r) => r.data)

      localStorage.setItem('operan_token', response.access_token)
      const failures: string[] = []
      if (hasBankData) {
        const bankPayload: BankAccountPayload = {
          ...bank,
          holder_name: bank.holder_name || form.full_name,
          holder_cpf: bank.holder_cpf || form.cpf || undefined,
          pix_key_type: bank.pix_key_type || undefined,
          pix_key: bank.pix_key || undefined,
        }
        try {
          await api.post('/account/bank-accounts', bankPayload)
        } catch {
          failures.push('dados bancarios')
        }
      }
      if (hasFamilyData) {
        const familyPayload: FamilyMemberPayload = {
          ...family,
          birth_date: family.birth_date || undefined,
          phone: family.phone || undefined,
          cpf: family.cpf || undefined,
          authorization_reference: family.authorization_reference || undefined,
          notes: family.notes || undefined,
        }
        try {
          await api.post('/account/family-members', familyPayload)
        } catch {
          failures.push('dados familiares')
        }
      }
      for (const document of documents) {
        const data = new FormData()
        data.append('file', document.file)
        data.append('document_type', document.type)
        try {
          await api.post('/documents/me', data, {
            headers: { 'Content-Type': 'multipart/form-data' },
          })
        } catch {
          failures.push(document.file.name)
        }
      }
      return { response, failures }
    },
    onSuccess: ({ response, failures }) => {
      const goHome = () => {
        queryClient.clear()
        navigate(homePathForUser(response.user), { replace: true })
      }
      if (failures.length) {
        setWarning(
          `Conta criada, mas alguns dados complementares nao puderam ser salvos: ${failures.join(
            ', '
          )}. Revise em Minha Conta.`
        )
        window.setTimeout(goHome, 3000)
        return
      }
      goHome()
    },
    onError: (err) => setError(getApiErrorMessage(err, 'Nao foi possivel aceitar o convite.')),
  })

  const requiresAccount = validation.data?.requires_account ?? true
  const loggedEmail = (user?.email || '').trim().toLowerCase()
  const formEmail = form.email.trim().toLowerCase()
  const creatingAccount = isPublicLink
    ? !loggedEmail || formEmail !== loggedEmail
    : requiresAccount
  const needsPassword = creatingAccount
  const existingAvatar = Boolean(account.data?.profile.has_avatar)
  const avatarMissing = !avatarBase64 && !existingAvatar
  const publicValidation = isPublicLink
    ? (validation.data as PublicInvitationValidation | undefined)
    : undefined

  const update = (field: keyof typeof initialState, value: string) =>
    setForm((current) => ({ ...current, [field]: value }))

  const updateBank = (field: keyof typeof initialBank, value: string | boolean) =>
    setBank((current) => ({ ...current, [field]: value }))

  const updateFamily = (field: keyof typeof initialFamily, value: string | boolean) =>
    setFamily((current) => ({ ...current, [field]: value }))

  const selectAvatar = async (file: File | null) => {
    setError('')
    if (!file) return
    if (!file.type.startsWith('image/')) {
      setError('Selecione uma imagem para a foto de perfil.')
      return
    }
    if (file.size > MAX_AVATAR_SOURCE_BYTES) {
      setError('A foto de perfil deve ter no maximo 25 MB.')
      return
    }
    setAvatarProcessing(true)
    try {
      const compressed = await compressImage(file, 1600, 0.85)
      if (compressed.size > MAX_AVATAR_BYTES) {
        setError('A foto de perfil deve ter no maximo 5 MB apos o processamento.')
        return
      }
      const result = await fileToDataUrl(compressed)
      setAvatarPreview(result)
      setAvatarBase64(result.split(',')[1] || '')
      setAvatarMimeType(compressed.type)
    } catch {
      setError('Nao foi possivel processar esta imagem. Tente outra foto.')
    } finally {
      setAvatarProcessing(false)
    }
  }

  const addDocumentFile = async (file: File | null) => {
    setError('')
    if (!file) return
    const isPdf = file.type === 'application/pdf'
    if (!isPdf && !file.type.startsWith('image/')) {
      setError('Envie um PDF ou uma imagem do documento.')
      return
    }
    if (file.size > MAX_DOCUMENT_BYTES) {
      setError('Cada documento deve ter no maximo 10 MB.')
      return
    }
    setDocumentProcessing(true)
    try {
      const prepared = isPdf ? file : await compressImage(file, 2400, 0.85)
      if (prepared.size > MAX_DOCUMENT_BYTES) {
        setError('Cada documento deve ter no maximo 10 MB.')
        return
      }
      setDocuments((current) => [...current, { type: documentType, file: prepared }])
    } catch {
      setError('Nao foi possivel processar este documento. Tente outro arquivo.')
    } finally {
      setDocumentProcessing(false)
    }
  }

  const removeDocument = (index: number) =>
    setDocuments((current) => current.filter((_, itemIndex) => itemIndex !== index))

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-4">
      <div className="w-full max-w-3xl">
        <div className="text-center mb-8">
          <div className="w-14 h-14 bg-violet-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <ShieldCheck className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white">Convite OPERAN</h1>
          <p className="text-gray-400 mt-1">Complete seu perfil e ative sua jornada</p>
        </div>

        <Card>
          {!token || validation.isLoading ? (
            <div className="flex justify-center py-10">
              <div className="animate-spin w-8 h-8 border-2 border-violet-600 border-t-transparent rounded-full" />
            </div>
          ) : validation.isError || !validation.data ? (
            <div className="text-center py-8">
              <p className="text-red-400 font-semibold">Convite invalido ou inexistente.</p>
              <Link className="text-violet-400 text-sm mt-3 inline-block" to="/login">
                Ir para o login
              </Link>
            </div>
          ) : !validation.data.valid ? (
            <div className="text-center py-8">
              <p className="text-yellow-400 font-semibold">
                Este convite esta {validation.data.status.toLowerCase()}.
              </p>
              <Link className="text-violet-400 text-sm mt-3 inline-block" to="/login">
                Ir para o login
              </Link>
            </div>
          ) : (
            <div className="space-y-6">
              <div className="rounded-2xl bg-gray-950 border border-gray-800 p-4 space-y-2">
                {'email' in validation.data && (
                  <p className="flex items-center gap-2 text-gray-300 text-sm">
                    <Mail className="w-4 h-4 text-violet-400" />
                    {validation.data.email}
                  </p>
                )}
                {user && (
                  <p className="flex items-center gap-2 text-gray-300 text-sm">
                    <Mail className="w-4 h-4 text-violet-400" />
                    {user.email}
                  </p>
                )}
                {publicValidation && (
                  <p className="flex items-center gap-2 text-gray-300 text-sm">
                    <Users className="w-4 h-4 text-emerald-400" />
                    Link publico compartilhavel - {publicValidation.uses_count} uso(s)
                    {publicValidation.max_uses
                      ? ` de ${publicValidation.max_uses}`
                      : ' ilimitados'}
                    {publicValidation.organization_name
                      ? ` - ${publicValidation.organization_name}`
                      : ''}
                  </p>
                )}
                <p className="flex items-center gap-2 text-gray-300 text-sm">
                  <Building2 className="w-4 h-4 text-violet-400" />
                  {validation.data.journey_type === 'LOCATIONS'
                    ? 'Jornada de Representante de Escola'
                    : 'Jornada de Profissional'}
                  {validation.data.location_name ? ` - ${validation.data.location_name}` : ''}
                </p>
                {requiredCategories.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {requiredCategories.map((category) => (
                      <span
                        key={category}
                        className="rounded-full bg-violet-500/10 border border-violet-500/30 px-2 py-0.5 text-[11px] text-violet-200"
                      >
                        {CATEGORY_LABELS[category] ?? category}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {!requiresAccount && !authLoading && !user && (
                <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/10 p-4 text-sm text-yellow-200">
                  {isPublicLink
                    ? 'Entre com sua conta para aceitar este link.'
                    : 'Ja existe uma conta com este e-mail. Entre com sua conta para aceitar o convite.'}
                  <Link className="block text-yellow-100 underline mt-2" to="/login">
                    Entrar
                  </Link>
                </div>
              )}

              <div className="space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-white">
                    Etapa {step} de {STEPS.length}: {STEPS[step - 1].title}
                  </p>
                  <p className="text-xs text-violet-300">
                    {Math.round((step / STEPS.length) * 100)}%
                  </p>
                </div>
                <div className="h-1.5 rounded-full bg-gray-800 overflow-hidden">
                  <div
                    className="h-full bg-violet-500 transition-all duration-300"
                    style={{ width: `${(step / STEPS.length) * 100}%` }}
                  />
                </div>
                <p className="text-xs text-gray-500">{STEPS[step - 1].hint}</p>
              </div>

              <>
                <div className={step === 1 ? 'space-y-6' : 'hidden'}>
                  <div>
                    <h2 className="text-sm font-bold text-white mb-3">
                      {creatingAccount
                        ? 'Crie seu acesso e perfil'
                        : 'Atualize seus dados'}
                    </h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {isPublicLink ? (
                        <Input
                          label="E-mail do participante"
                          type="email"
                          value={form.email}
                          onChange={(e) => update('email', e.target.value)}
                          autoComplete="email"
                          required
                        />
                      ) : (
                        'email' in validation.data && (
                          <Input
                            label="E-mail do convite"
                            type="email"
                            value={validation.data.email}
                            disabled
                          />
                        )
                      )}
                      {needsPassword && (
                        <Input
                          label="Crie sua senha"
                          type="password"
                          value={form.password}
                          onChange={(e) => update('password', e.target.value)}
                          autoComplete="new-password"
                          minLength={8}
                          required
                        />
                      )}
                      {needsPassword && (
                        <p className="md:col-span-2 text-xs text-gray-500 -mt-1">
                          Este e-mail e senha serao usados pelo participante para entrar na
                          plataforma. A senha deve ter ao menos 8 caracteres.
                        </p>
                      )}
                      {isPublicLink && user && !needsPassword && (
                        <p className="md:col-span-2 text-xs text-emerald-400 -mt-1">
                          Voce esta logado com este e-mail. O convite sera vinculado a sua conta
                          atual.
                        </p>
                      )}
                      <Input
                        label="Nome completo"
                        value={form.full_name}
                        onChange={(e) => update('full_name', e.target.value)}
                        required
                      />
                      <Input
                        label="Nome social"
                        value={form.social_name}
                        onChange={(e) => update('social_name', e.target.value)}
                      />
                      {account.data?.profile && !creatingAccount ? (
                        <Input
                          label="CPF"
                          value={account.data.profile.cpf_masked}
                          disabled
                        />
                      ) : (
                        <Input
                          label="CPF"
                          value={form.cpf}
                          onChange={(e) => update('cpf', e.target.value)}
                          required
                        />
                      )}
                      <Input
                        label="RG"
                        value={form.rg}
                        onChange={(e) => update('rg', e.target.value)}
                      />
                      <Input
                        label="Data de nascimento"
                        type="date"
                        value={form.birth_date}
                        onChange={(e) => update('birth_date', e.target.value)}
                        required
                      />
                      <Input
                        label="Genero"
                        value={form.gender}
                        onChange={(e) => update('gender', e.target.value)}
                      />
                      <Input
                        label="Telefone"
                        value={form.phone}
                        onChange={(e) => update('phone', e.target.value)}
                        required
                      />
                    </div>
                  </div>

                  <div className="rounded-xl border border-violet-500/30 bg-violet-500/5 p-4">
                    <h2 className="text-sm font-bold text-white mb-1">
                      Foto de perfil <span className="text-red-400">*</span>
                    </h2>
                    <p className="text-xs text-gray-500 mb-3">
                      Obrigatoria. Tire uma foto na hora ou escolha uma imagem da galeria. A
                      imagem sera otimizada, armazenada criptografada e usada na sua
                      identificacao operacional.
                    </p>
                    <div className="flex flex-col sm:flex-row sm:items-center gap-4">
                      <div className="w-24 h-24 rounded-2xl border border-gray-700 bg-gray-950 overflow-hidden flex items-center justify-center shrink-0">
                        {avatarPreview ? (
                          <img
                            src={avatarPreview}
                            alt="Previa da foto de perfil"
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <Camera className="w-8 h-8 text-gray-600" />
                        )}
                      </div>
                      <div className="flex-1 space-y-2">
                        <input
                          ref={avatarCameraRef}
                          type="file"
                          accept="image/*"
                          capture="user"
                          className="hidden"
                          onChange={(e) => {
                            const file = e.target.files?.[0] || null
                            e.target.value = ''
                            void selectAvatar(file)
                          }}
                        />
                        <input
                          ref={avatarUploadRef}
                          type="file"
                          accept="image/*"
                          className="hidden"
                          onChange={(e) => {
                            const file = e.target.files?.[0] || null
                            e.target.value = ''
                            void selectAvatar(file)
                          }}
                        />
                        <div className="flex flex-wrap gap-2">
                          <Button
                            type="button"
                            variant="secondary"
                            onClick={() => avatarCameraRef.current?.click()}
                          >
                            <Camera className="w-4 h-4 mr-2" />
                            Tirar foto
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            onClick={() => avatarUploadRef.current?.click()}
                          >
                            <Upload className="w-4 h-4 mr-2" />
                            Escolher arquivo
                          </Button>
                        </div>
                        {avatarProcessing && (
                          <p className="text-xs text-violet-300">Processando foto...</p>
                        )}
                        {existingAvatar && !avatarBase64 && (
                          <p className="text-xs text-emerald-400">
                            Voce ja possui uma foto cadastrada. Tire outra para substituir.
                          </p>
                        )}
                        {avatarMissing && !avatarProcessing && (
                          <p className="text-xs text-yellow-400">
                            Tire ou selecione uma foto para continuar.
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                </div>

                <div className={step === 2 ? 'space-y-6' : 'hidden'}>
                  <div>
                    <h2 className="text-sm font-bold text-white mb-3">Endereco</h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <Input
                        label="CEP"
                        value={form.zip_code}
                        onChange={(e) => update('zip_code', e.target.value)}
                      />
                      <Input
                        label="Cidade"
                        value={form.city}
                        onChange={(e) => update('city', e.target.value)}
                        required
                      />
                      <Input
                        label="UF"
                        maxLength={2}
                        value={form.state}
                        onChange={(e) => update('state', e.target.value.toUpperCase())}
                        required
                      />
                      <Input
                        label="Bairro"
                        value={form.address_neighborhood}
                        onChange={(e) => update('address_neighborhood', e.target.value)}
                      />
                      <Input
                        label="Logradouro"
                        value={form.address_street}
                        onChange={(e) => update('address_street', e.target.value)}
                      />
                      <Input
                        label="Numero"
                        value={form.address_number}
                        onChange={(e) => update('address_number', e.target.value)}
                      />
                      <Input
                        label="Complemento"
                        value={form.address_complement}
                        onChange={(e) => update('address_complement', e.target.value)}
                      />
                    </div>
                  </div>

                  <div>
                    <h2 className="text-sm font-bold text-white mb-3">Contato de emergencia</h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <Input
                        label="Nome"
                        value={form.emergency_contact_name}
                        onChange={(e) => update('emergency_contact_name', e.target.value)}
                      />
                      <Input
                        label="Telefone"
                        value={form.emergency_contact_phone}
                        onChange={(e) => update('emergency_contact_phone', e.target.value)}
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-gray-400 mb-1.5">
                      Bio / observacoes
                    </label>
                    <textarea
                      className="w-full bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-violet-500 min-h-20"
                      value={form.bio}
                      onChange={(e) => update('bio', e.target.value)}
                    />
                  </div>
                </div>

                <div className={step === 3 ? 'space-y-6' : 'hidden'}>
                  <div className="rounded-xl border border-gray-800 p-4">
                    <h2 className="text-sm font-bold text-white mb-1">
                      Dados bancarios
                      {needsBank && <span className="text-red-400"> *</span>}
                    </h2>
                    <p className="text-xs text-gray-500 mb-3">
                      Opcional para o cadastro; necessario para pagamentos de missoes.
                    </p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <Input
                        label="Banco"
                        value={bank.bank_name}
                        onChange={(e) => updateBank('bank_name', e.target.value)}
                        required={needsBank}
                      />
                      <Input
                        label="Codigo do banco"
                        value={bank.bank_code}
                        onChange={(e) => updateBank('bank_code', e.target.value)}
                        required={needsBank}
                      />
                      <Input
                        label="Agencia"
                        value={bank.branch}
                        onChange={(e) => updateBank('branch', e.target.value)}
                        required={needsBank}
                      />
                      <Input
                        label="Conta"
                        value={bank.account_number}
                        onChange={(e) => updateBank('account_number', e.target.value)}
                        required={needsBank}
                      />
                      <div>
                        <label className="block text-xs font-semibold text-gray-400 mb-1.5">
                          Tipo de conta
                        </label>
                        <select
                          className="w-full bg-gray-950 border border-gray-800 rounded-xl px-3 py-2.5 text-sm text-white"
                          value={bank.account_type}
                          onChange={(e) => updateBank('account_type', e.target.value)}
                        >
                          <option value="CHECKING">Conta corrente</option>
                          <option value="SAVINGS">Poupanca</option>
                          <option value="PAYMENT">Conta de pagamento</option>
                        </select>
                      </div>
                      <Input
                        label="Titular"
                        placeholder={form.full_name || 'Nome do titular'}
                        value={bank.holder_name}
                        onChange={(e) => updateBank('holder_name', e.target.value)}
                        required={needsBank}
                      />
                      <Input
                        label="CPF do titular"
                        value={bank.holder_cpf}
                        onChange={(e) => updateBank('holder_cpf', e.target.value)}
                      />
                      <div>
                        <label className="block text-xs font-semibold text-gray-400 mb-1.5">
                          Tipo de chave Pix
                        </label>
                        <select
                          className="w-full bg-gray-950 border border-gray-800 rounded-xl px-3 py-2.5 text-sm text-white"
                          value={bank.pix_key_type}
                          onChange={(e) => updateBank('pix_key_type', e.target.value)}
                        >
                          <option value="">Sem Pix</option>
                          <option value="CPF">CPF</option>
                          <option value="CNPJ">CNPJ</option>
                          <option value="EMAIL">E-mail</option>
                          <option value="PHONE">Telefone</option>
                          <option value="RANDOM">Aleatoria</option>
                        </select>
                      </div>
                      {bank.pix_key_type && (
                        <Input
                          label="Chave Pix"
                          value={bank.pix_key}
                          onChange={(e) => updateBank('pix_key', e.target.value)}
                        />
                      )}
                    </div>
                  </div>

                  <div className="rounded-xl border border-gray-800 p-4">
                    <h2 className="text-sm font-bold text-white mb-1">
                      Familiar / contato de confianca
                      {needsFamily && <span className="text-red-400"> *</span>}
                    </h2>
                    <p className="text-xs text-gray-500 mb-3">
                      Opcional. Voce pode adicionar outros familiares depois em Minha Conta.
                    </p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <Input
                        label="Nome completo"
                        value={family.full_name}
                        onChange={(e) => updateFamily('full_name', e.target.value)}
                        required={needsFamily}
                      />
                      <Input
                        label="Parentesco"
                        placeholder="Ex: MAE, PAI, CONJUGE"
                        value={family.kinship}
                        onChange={(e) => updateFamily('kinship', e.target.value)}
                        required={needsFamily}
                      />
                      <Input
                        label="Data de nascimento"
                        type="date"
                        value={family.birth_date}
                        onChange={(e) => updateFamily('birth_date', e.target.value)}
                      />
                      <Input
                        label="Telefone"
                        value={family.phone}
                        onChange={(e) => updateFamily('phone', e.target.value)}
                      />
                      <Input
                        label="CPF"
                        value={family.cpf}
                        onChange={(e) => updateFamily('cpf', e.target.value)}
                      />
                      <Input
                        label="Referencia de autorizacao"
                        value={family.authorization_reference}
                        onChange={(e) =>
                          updateFamily('authorization_reference', e.target.value)
                        }
                      />
                    </div>
                    <label className="flex items-center gap-2 mt-3 text-xs text-gray-400">
                      <input
                        type="checkbox"
                        className="accent-violet-600"
                        checked={family.is_legal_guardian}
                        onChange={(e) =>
                          updateFamily('is_legal_guardian', e.target.checked)
                        }
                      />
                      E responsavel legal
                    </label>
                  </div>
                </div>

                <div className={step === 4 ? 'space-y-6' : 'hidden'}>
                  <div className="rounded-xl border border-gray-800 p-4">
                    <h2 className="text-sm font-bold text-white mb-1">
                      Documentos
                      {needsDocuments && <span className="text-red-400"> *</span>}
                    </h2>
                    <p className="text-xs text-gray-500 mb-3">
                      Tire uma foto do documento na hora ou envie um PDF/imagem. Fotos sao
                      otimizadas automaticamente. Limite de 10 MB por arquivo.
                    </p>
                    <div className="flex flex-wrap items-end gap-3">
                      <div>
                        <label className="block text-xs font-semibold text-gray-400 mb-1.5">
                          Tipo
                        </label>
                        <select
                          className="bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-sm text-white"
                          value={documentType}
                          onChange={(e) => setDocumentType(e.target.value)}
                        >
                          {DOCUMENT_TYPES.map((type) => (
                            <option key={type} value={type}>
                              {type}
                            </option>
                          ))}
                        </select>
                      </div>
                      <input
                        ref={documentCameraRef}
                        type="file"
                        accept="image/*"
                        capture="environment"
                        className="hidden"
                        onChange={(e) => {
                          const file = e.target.files?.[0] || null
                          e.target.value = ''
                          void addDocumentFile(file)
                        }}
                      />
                      <input
                        ref={documentUploadRef}
                        type="file"
                        accept="application/pdf,image/*"
                        className="hidden"
                        onChange={(e) => {
                          const file = e.target.files?.[0] || null
                          e.target.value = ''
                          void addDocumentFile(file)
                        }}
                      />
                      <Button
                        type="button"
                        variant="secondary"
                        onClick={() => documentCameraRef.current?.click()}
                      >
                        <Camera className="w-4 h-4 mr-2" />
                        Fotografar documento
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        onClick={() => documentUploadRef.current?.click()}
                      >
                        <Upload className="w-4 h-4 mr-2" />
                        Enviar arquivo
                      </Button>
                    </div>
                    {documentProcessing && (
                      <p className="text-xs text-violet-300 mt-2">
                        Processando documento...
                      </p>
                    )}
                    {documents.length > 0 && (
                      <ul className="divide-y divide-gray-800 mt-3">
                        {documents.map((document, index) => (
                          <li
                            key={`${document.file.name}-${index}`}
                            className="py-2 flex items-center justify-between gap-3"
                          >
                            <span className="text-sm text-white flex items-center gap-2 min-w-0">
                              <FileText className="w-4 h-4 text-gray-500 shrink-0" />
                              <span className="truncate">{document.file.name}</span>
                              <span className="text-xs text-gray-500">{document.type}</span>
                            </span>
                            <button
                              type="button"
                              className="text-gray-500 hover:text-red-400"
                              onClick={() => removeDocument(index)}
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              </>

              {error && (
                <p className="text-red-400 text-sm bg-red-400/10 border border-red-400/20 rounded-lg px-3 py-2">
                  {error}
                </p>
              )}
              {warning && (
                <p className="text-yellow-300 text-sm bg-yellow-500/10 border border-yellow-500/20 rounded-lg px-3 py-2">
                  {warning}
                </p>
              )}
              {draftMessage && (
                <p className="text-emerald-300 text-sm bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2">
                  {draftMessage}
                  {draftSavedAt ? ` Ultimo salvamento: ${draftSavedAt}.` : ''}
                </p>
              )}

              <div className="flex flex-col-reverse sm:flex-row sm:items-center sm:justify-between gap-2">
                <Button
                  variant="secondary"
                  disabled={step === 1}
                  onClick={goBack}
                >
                  Voltar
                </Button>
                <div className="flex flex-col sm:flex-row gap-2">
                  <Button
                    variant="ghost"
                    loading={saveDraft.isPending}
                    onClick={() => {
                      setDraftMessage('')
                      setError('')
                      saveDraft.mutate()
                    }}
                  >
                    <FileText className="w-4 h-4 mr-2" />
                    Salvar rascunho
                  </Button>
                  {step < STEPS.length && (
                    <Button onClick={goNext}>Continuar</Button>
                  )}
                </div>
              </div>

              {draftSavedAt && (
                <p className="text-xs text-gray-500">
                  Rascunho de {draftSavedAt}
                </p>
              )}

              {step === STEPS.length && (
                <>
                  <label className="flex items-start gap-3 text-xs text-gray-400">
                    <input
                      type="checkbox"
                      checked={consent}
                      onChange={(e) => setConsent(e.target.checked)}
                      className="mt-0.5 accent-violet-600"
                    />
                    <span>
                      Declaro que os dados informados sao verdadeiros e autorizo o tratamento dos
                      dados pessoais, documentos e foto de perfil para execucao das atividades
                      operacionais da OPERAN.
                    </span>
                  </label>

                  <Button
                    className="w-full"
                    size="lg"
                    loading={accept.isPending}
                    disabled={
                      (!requiresAccount && !user) ||
                      avatarMissing ||
                      !consent ||
                      (needsBank && !bankReady) ||
                      (needsFamily && !familyReady) ||
                      (needsDocuments && documents.length === 0)
                    }
                    onClick={() => {
                      setError('')
                      setWarning('')
                      if (!consent) {
                        setError('E necessario aceitar a politica de privacidade e o tratamento de dados.')
                        return
                      }
                      if (avatarMissing) {
                        setError('A foto de perfil e obrigatoria.')
                        return
                      }
                      if (needsBank && !bankReady) {
                        setError('Preencha os dados bancarios solicitados neste convite.')
                        return
                      }
                      if (needsFamily && !familyReady) {
                        setError('Informe ao menos nome e parentesco do familiar solicitado.')
                        return
                      }
                      if (needsDocuments && documents.length === 0) {
                        setError('Anexe ao menos um documento solicitado neste convite.')
                        return
                      }
                      accept.mutate()
                    }}
                  >
                    <CheckCircle2 className="w-4 h-4 mr-2" />
                    Aceitar convite
                  </Button>

                  <p className="text-center text-gray-500 text-xs">
                    Ao aceitar, voce concorda com a politica de privacidade e o tratamento de dados
                    para execucao das atividades operacionais.
                  </p>
                </>
              )}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
