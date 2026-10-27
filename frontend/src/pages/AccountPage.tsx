import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  BadgeCheck,
  FileText,
  GraduationCap,
  MapPin,
  Save,
  School,
  Upload,
  UserRound,
  Camera,
} from 'lucide-react'
import api from '../api/client'
import { BankAccountsCard } from '../components/account/BankAccountsCard'
import { FamilyMembersCard } from '../components/account/FamilyMembersCard'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { useAuth } from '../hooks/useAuth'
import { getApiErrorMessage } from '../lib/errors'
import { downloadDocument } from '../lib/download'
import type { Account, DocumentItem, PersonProfile, PersonProfileUpdatePayload } from '../types'

type ProfileForm = {
  full_name: string
  social_name: string
  phone: string
  city: string
  state: string
  zip_code: string
  address_street: string
  address_number: string
  address_neighborhood: string
  emergency_contact_name: string
  emergency_contact_phone: string
  bio: string
}

const emptyForm: ProfileForm = {
  full_name: '',
  social_name: '',
  phone: '',
  city: '',
  state: '',
  zip_code: '',
  address_street: '',
  address_number: '',
  address_neighborhood: '',
  emergency_contact_name: '',
  emergency_contact_phone: '',
  bio: '',
}

function formFromProfile(profile: PersonProfile): ProfileForm {
  return {
    full_name: profile.full_name || '',
    social_name: profile.social_name || '',
    phone: '',
    city: profile.city || '',
    state: profile.state || '',
    zip_code: profile.zip_code || '',
    address_street: profile.address_street || '',
    address_number: profile.address_number || '',
    address_neighborhood: profile.address_neighborhood || '',
    emergency_contact_name: profile.emergency_contact_name || '',
    emergency_contact_phone: '',
    bio: profile.bio || '',
  }
}

export function AccountPage() {
  const { user, refetchUser } = useAuth()
  const queryClient = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const avatarRef = useRef<HTMLInputElement>(null)
  const [avatarPreview, setAvatarPreview] = useState('')
  const [form, setForm] = useState<ProfileForm>(emptyForm)
  const [documentType, setDocumentType] = useState('RG')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const account = useQuery({
    queryKey: ['account-me'],
    queryFn: () => api.get<Account>('/account/me').then((r) => r.data),
    retry: false,
  })

  const documents = useQuery({
    queryKey: ['my-documents'],
    queryFn: () => api.get<DocumentItem[]>('/documents/me').then((r) => r.data),
  })

  useEffect(() => {
    if (account.data?.profile) setForm(formFromProfile(account.data.profile))
  }, [account.data])

  useEffect(() => {
    let objectUrl = ''
    if (!account.data?.profile.has_avatar) {
      setAvatarPreview('')
      return
    }
    api
      .get('/account/avatar', { responseType: 'blob' })
      .then((response) => {
        objectUrl = URL.createObjectURL(response.data)
        setAvatarPreview(objectUrl)
      })
      .catch(() => setAvatarPreview(''))
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [account.data?.profile.has_avatar, account.data?.profile.avatar_url])

  const saveProfile = useMutation({
    mutationFn: () => {
      const payload: PersonProfileUpdatePayload = {}
      Object.entries(form).forEach(([key, value]) => {
        if (!value) return
        if (key === 'phone' && (value === '' || value === account.data?.profile.phone_masked)) return
        payload[key as keyof PersonProfileUpdatePayload] = value
      })
      return api.patch<PersonProfile>('/account/profile', payload).then((r) => r.data)
    },
    onSuccess: () => {
      setMessage('Perfil atualizado.')
      setError('')
      queryClient.invalidateQueries({ queryKey: ['account-me'] })
      refetchUser()
    },
    onError: (err) => {
      setMessage('')
      setError(getApiErrorMessage(err, 'Nao foi possivel atualizar o perfil.'))
    },
  })

  const uploadAvatar = useMutation({
    mutationFn: async (file: File) => {
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(String(reader.result || ''))
        reader.onerror = () => reject(new Error('Falha ao ler a imagem.'))
        reader.readAsDataURL(file)
      })
      return api
        .post<PersonProfile>('/account/avatar', {
          avatar_base64: dataUrl.split(',')[1] || '',
          avatar_mime_type: file.type,
        })
        .then((r) => r.data)
    },
    onSuccess: () => {
      setMessage('Foto de perfil atualizada.')
      setError('')
      queryClient.invalidateQueries({ queryKey: ['account-me'] })
      if (avatarRef.current) avatarRef.current.value = ''
    },
    onError: (err) => {
      setMessage('')
      setError(getApiErrorMessage(err, 'Nao foi possivel atualizar a foto.'))
    },
  })

  const upload = useMutation({
    mutationFn: (file: File) => {
      const data = new FormData()
      data.append('file', file)
      data.append('document_type', documentType)
      return api
        .post<DocumentItem>('/documents/me', data, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        .then((r) => r.data)
    },
    onSuccess: () => {
      setMessage('Documento enviado para analise.')
      setError('')
      queryClient.invalidateQueries({ queryKey: ['my-documents'] })
      if (fileRef.current) fileRef.current.value = ''
    },
    onError: (err) => {
      setMessage('')
      setError(getApiErrorMessage(err, 'Nao foi possivel enviar o documento.'))
    },
  })

  const update = (field: keyof ProfileForm, value: string) =>
    setForm((current) => ({ ...current, [field]: value }))

  const profile = account.data?.profile
  const journeys = account.data?.journeys ?? user?.journeys ?? []
  const qualifications = account.data?.qualifications ?? user?.qualifications ?? []

  if (account.isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin w-8 h-8 border-2 border-violet-600 border-t-transparent rounded-full" />
      </div>
    )
  }

  if (account.isError || !profile) {
    return (
      <Card className="text-center py-16">
        <UserRound className="w-12 h-12 text-gray-700 mx-auto mb-3" />
        <p className="text-white font-semibold">Perfil global nao cadastrado</p>
        <p className="text-gray-500 text-sm mt-1 max-w-md mx-auto">
          Sua conta existe, mas o perfil pessoal ainda nao foi criado. Ele e criado ao aceitar um
          convite ou ao importar um cadastro legado de profissional.
        </p>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black text-white flex items-center gap-3">
          <div className="w-9 h-9 bg-violet-600 rounded-xl flex items-center justify-center text-white">
            <UserRound className="w-5 h-5" />
          </div>
          Minha Conta Global
        </h1>
        <p className="text-gray-400 text-sm mt-0.5">
          Dados pessoais compartilhados por todas as suas jornadas na OPERAN.
        </p>
      </div>

      {(message || error) && (
        <div
          className={`rounded-xl px-4 py-3 text-sm border ${
            error
              ? 'bg-red-500/10 border-red-500/30 text-red-300'
              : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
          }`}
        >
          {error || message}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <Card className="xl:col-span-2">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-white font-bold">Dados pessoais</h2>
            <span
              className={`text-xs font-bold px-2.5 py-1 rounded-full border ${
                profile.profile_completed
                  ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
                  : 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20'
              }`}
            >
              {profile.profile_completed ? 'Completo' : 'Incompleto'}
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input label="Nome completo" value={form.full_name} onChange={(e) => update('full_name', e.target.value)} />
            <Input label="Nome social" value={form.social_name} onChange={(e) => update('social_name', e.target.value)} />
            <Input label="E-mail" value={profile.email} disabled />
            <Input label="CPF" value={profile.cpf_masked} disabled />
            <Input
              label="Telefone"
              placeholder={profile.phone_masked}
              value={form.phone}
              onChange={(e) => update('phone', e.target.value)}
            />
            <Input label="Cidade" value={form.city} onChange={(e) => update('city', e.target.value)} />
            <Input label="UF" maxLength={2} value={form.state} onChange={(e) => update('state', e.target.value.toUpperCase())} />
            <Input label="CEP" value={form.zip_code} onChange={(e) => update('zip_code', e.target.value)} />
            <Input label="Endereco" value={form.address_street} onChange={(e) => update('address_street', e.target.value)} />
            <Input label="Numero" value={form.address_number} onChange={(e) => update('address_number', e.target.value)} />
            <Input label="Bairro" value={form.address_neighborhood} onChange={(e) => update('address_neighborhood', e.target.value)} />
            <Input
              label="Contato de emergencia"
              value={form.emergency_contact_name}
              onChange={(e) => update('emergency_contact_name', e.target.value)}
            />
            <Input
              label="Telefone de emergencia"
              placeholder={profile.emergency_contact_phone_masked}
              value={form.emergency_contact_phone}
              onChange={(e) => update('emergency_contact_phone', e.target.value)}
            />
          </div>
          <div className="mt-4">
            <label className="block text-xs font-semibold text-gray-400 mb-1.5">Bio</label>
            <textarea
              className="w-full bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-violet-500 min-h-24"
              value={form.bio}
              onChange={(e) => update('bio', e.target.value)}
            />
          </div>
          <Button
            className="mt-5"
            loading={saveProfile.isPending}
            onClick={() => {
              setMessage('')
              setError('')
              saveProfile.mutate()
            }}
          >
            <Save className="w-4 h-4 mr-2" />
            Salvar perfil
          </Button>
        </Card>

        <div className="space-y-6">
          <Card>
            <h2 className="text-white font-bold mb-4">Minhas jornadas</h2>
            <div className="space-y-3">
              <JourneyRow
                active={journeys.some(
                  (j) => j.journey_type === 'PROFESSIONALS' && j.status === 'ACTIVE'
                )}
                icon={GraduationCap}
                title="Rede de Profissionais"
                description="Qualificacoes, Academy e missoes."
              />
              <JourneyRow
                active={journeys.some(
                  (j) => j.journey_type === 'LOCATIONS' && j.status === 'ACTIVE'
                )}
                icon={School}
                title="Rede de Locais"
                description="Representacao de escolas e workflow."
              />
            </div>
          </Card>

          <Card>
            <h2 className="text-white font-bold mb-4">Qualificacoes</h2>
            {qualifications.length === 0 ? (
              <p className="text-gray-500 text-sm">
                Nenhuma qualificacao profissional ativa.
              </p>
            ) : (
              <ul className="space-y-2">
                {qualifications.map((qualification) => (
                  <li
                    key={qualification.id}
                    className="rounded-xl border border-gray-800 bg-gray-950 px-3 py-2"
                  >
                    <p className="text-sm font-semibold text-white flex items-center gap-2">
                      <BadgeCheck className="w-4 h-4 text-violet-400" />
                      {qualification.function_name}
                    </p>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {qualification.status}
                      {qualification.expires_at
                        ? ` - validade ${new Date(qualification.expires_at).toLocaleDateString('pt-BR')}`
                        : ''}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <BankAccountsCard />
        <FamilyMembersCard />
      </div>

      <Card>
        <h2 className="text-white font-bold mb-1">Documentos pessoais</h2>
        <p className="text-gray-500 text-sm mb-4">PDF, JPEG ou PNG, ate 10 MB.</p>
        <div className="flex flex-wrap items-end gap-3 mb-4">
          <div>
            <label className="block text-xs font-semibold text-gray-400 mb-1.5">Tipo</label>
            <select
              className="bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-sm text-white"
              value={documentType}
              onChange={(e) => setDocumentType(e.target.value)}
            >
              {['RG', 'CNH', 'CPF', 'PROOF_OF_ADDRESS', 'EDUCATION', 'HEALTH', 'CRIMINAL_RECORD', 'OTHER'].map(
                (type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                )
              )}
            </select>
          </div>
          <input ref={fileRef} type="file" accept="application/pdf,image/jpeg,image/png" className="text-sm text-gray-400" />
          <Button
            variant="secondary"
            loading={upload.isPending}
            onClick={() => {
              const file = fileRef.current?.files?.[0]
              if (!file) {
                setError('Selecione um arquivo.')
                return
              }
              setError('')
              upload.mutate(file)
            }}
          >
            <Upload className="w-4 h-4 mr-2" />
            Enviar documento
          </Button>
        </div>
        {documents.data?.length ? (
          <ul className="divide-y divide-gray-800">
            {documents.data.map((doc) => (
              <li key={doc.id} className="py-3 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm text-white truncate flex items-center gap-2">
                    <FileText className="w-4 h-4 text-gray-500" />
                    {doc.file_name}
                  </p>
                  <p className="text-xs text-gray-500">
                    {doc.document_type} - {doc.status}
                  </p>
                </div>
                <button
                  type="button"
                  className="text-xs text-violet-400 hover:underline"
                  onClick={() => downloadDocument(doc.download_path, doc.file_name)}
                >
                  Abrir
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-gray-500 text-sm">Nenhum documento enviado.</p>
        )}
      </Card>
    </div>
  )
}

function JourneyRow({
  active,
  icon: Icon,
  title,
  description,
}: {
  active: boolean
  icon: typeof MapPin
  title: string
  description: string
}) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-gray-800 bg-gray-950 p-3">
      <div
        className={`w-9 h-9 rounded-lg flex items-center justify-center ${
          active ? 'bg-violet-600/20 text-violet-400' : 'bg-gray-800 text-gray-500'
        }`}
      >
        <Icon className="w-4 h-4" />
      </div>
      <div className="min-w-0">
        <p className={`text-sm font-semibold ${active ? 'text-white' : 'text-gray-400'}`}>
          {title}
        </p>
        <p className="text-xs text-gray-500">{description}</p>
      </div>
      <span
        className={`ml-auto text-[10px] font-bold px-2 py-0.5 rounded-full ${
          active
            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
            : 'bg-gray-800 text-gray-500'
        }`}
      >
        {active ? 'ATIVA' : 'INATIVA'}
      </span>
    </div>
  )
}
