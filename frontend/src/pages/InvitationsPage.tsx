import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Copy, Link2, MailPlus, RefreshCw, Users, XCircle } from 'lucide-react'
import api from '../api/client'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { useAuth } from '../hooks/useAuth'
import { getApiErrorMessage } from '../lib/errors'
import type {
  Invitation,
  InvitationPurpose,
  JourneyType,
  Location,
  Mission,
  Organization,
  ParticipantDataCategory,
  PublicInvitation,
} from '../types'

const DATA_CATEGORIES: { value: ParticipantDataCategory; label: string }[] = [
  { value: 'PROFILE', label: 'Perfil' },
  { value: 'CONTACT', label: 'Contato' },
  { value: 'ADDRESS', label: 'Endereco' },
  { value: 'BANK', label: 'Dados bancarios' },
  { value: 'FAMILY', label: 'Familia' },
  { value: 'DOCUMENTS', label: 'Documentos' },
  { value: 'QUALIFICATIONS', label: 'Qualificacoes' },
]

const PURPOSE_LABELS: Record<InvitationPurpose, string> = {
  GLOBAL_REGISTRATION: 'Cadastro global',
  PROFESSIONAL_NETWORK: 'Rede de profissionais',
  LOCATION_REPRESENTATIVE: 'Representante de local',
  MISSION_PARTICIPANT: 'Participante de missao',
}

export function InvitationsPage() {
  const { isAdmin } = useAuth()
  const queryClient = useQueryClient()
  const [email, setEmail] = useState('')
  const [journeyType, setJourneyType] = useState<JourneyType>('PROFESSIONALS')
  const [purpose, setPurpose] = useState<InvitationPurpose>('GLOBAL_REGISTRATION')
  const [missionId, setMissionId] = useState('')
  const [requiredCategories, setRequiredCategories] = useState<
    ParticipantDataCategory[]
  >(['PROFILE', 'CONTACT', 'ADDRESS'])
  const [locationId, setLocationId] = useState('')
  const [organizationId, setOrganizationId] = useState('')
  const [created, setCreated] = useState<Invitation | null>(null)
  const [createdPublic, setCreatedPublic] = useState<PublicInvitation | null>(null)
  const [mode, setMode] = useState<'INDIVIDUAL' | 'PUBLIC'>('INDIVIDUAL')
  const [label, setLabel] = useState('')
  const [maxUses, setMaxUses] = useState('')
  const [publicExpiresInDays, setPublicExpiresInDays] = useState(30)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const invitations = useQuery({
    queryKey: ['invitations'],
    queryFn: () => api.get<Invitation[]>('/invitations').then((r) => r.data),
  })

  const locations = useQuery({
    queryKey: ['invitation-locations'],
    queryFn: () => api.get<Location[]>('/locations').then((r) => r.data),
  })

  const publicInvitations = useQuery({
    queryKey: ['public-invitations'],
    queryFn: () => api.get<PublicInvitation[]>('/invitations/public').then((r) => r.data),
  })

  const organizations = useQuery({
    queryKey: ['invitation-organizations'],
    queryFn: () => api.get<Organization[]>('/organizations').then((r) => r.data),
    enabled: isAdmin,
  })

  const missions = useQuery({
    queryKey: ['invitation-missions'],
    queryFn: () => api.get<Mission[]>('/missions').then((r) => r.data),
    enabled: purpose === 'MISSION_PARTICIPANT',
  })

  const create = useMutation({
    mutationFn: () =>
      api
        .post<Invitation>('/invitations', {
          email,
          journey_type: journeyType,
          purpose,
          mission_id:
            purpose === 'MISSION_PARTICIPANT' && missionId ? missionId : undefined,
          required_data_categories: requiredCategories,
          location_id: journeyType === 'LOCATIONS' && locationId ? locationId : undefined,
          organization_id:
            isAdmin &&
            journeyType === 'PROFESSIONALS' &&
            purpose !== 'MISSION_PARTICIPANT' &&
            organizationId
              ? organizationId
              : undefined,
          expires_in_days: 7,
        })
        .then((r) => r.data),
    onSuccess: (data) => {
      setCreated(data)
      setEmail('')
      setLocationId('')
      setOrganizationId('')
      setMessage('Convite criado. Compartilhe o link com o destinatario.')
      setError('')
      queryClient.invalidateQueries({ queryKey: ['invitations'] })
    },
    onError: (err) => {
      setMessage('')
      setError(getApiErrorMessage(err, 'Nao foi possivel criar o convite.'))
    },
  })

  const createPublic = useMutation({
    mutationFn: () =>
      api
        .post<PublicInvitation>('/invitations/public', {
          label: label || undefined,
          journey_type: journeyType,
          purpose,
          mission_id:
            purpose === 'MISSION_PARTICIPANT' && missionId ? missionId : undefined,
          required_data_categories: requiredCategories,
          location_id: journeyType === 'LOCATIONS' && locationId ? locationId : undefined,
          organization_id:
            isAdmin &&
            journeyType === 'PROFESSIONALS' &&
            purpose !== 'MISSION_PARTICIPANT' &&
            organizationId
              ? organizationId
              : undefined,
          expires_in_days: publicExpiresInDays,
          max_uses: maxUses ? Number(maxUses) : undefined,
        })
        .then((r) => r.data),
    onSuccess: (data) => {
      setCreatedPublic(data)
      setCreated(null)
      setLabel('')
      setMaxUses('')
      setMessage('Link publico criado. Compartilhe com quantas pessoas quiser.')
      setError('')
      queryClient.invalidateQueries({ queryKey: ['public-invitations'] })
    },
    onError: (err) => {
      setMessage('')
      setError(getApiErrorMessage(err, 'Nao foi possivel criar o link publico.'))
    },
  })

  const revokePublic = useMutation({
    mutationFn: (id: string) => api.post(`/invitations/public/${id}/revoke`),
    onSuccess: () => {
      setMessage('Link publico revogado.')
      setError('')
      queryClient.invalidateQueries({ queryKey: ['public-invitations'] })
    },
    onError: (err) => setError(getApiErrorMessage(err, 'Nao foi possivel revogar o link.')),
  })

  const revoke = useMutation({
    mutationFn: (id: string) => api.post(`/invitations/${id}/revoke`),
    onSuccess: () => {
      setMessage('Convite revogado.')
      setError('')
      queryClient.invalidateQueries({ queryKey: ['invitations'] })
    },
    onError: (err) => setError(getApiErrorMessage(err, 'Nao foi possivel revogar.')),
  })

  const regenerate = useMutation({
    mutationFn: (id: string) =>
      api.post<Invitation>(`/invitations/${id}/regenerate`).then((r) => r.data),
    onSuccess: async (data) => {
      setCreated(data)
      setError('')
      queryClient.invalidateQueries({ queryKey: ['invitations'] })
      if (data.accept_path) {
        await navigator.clipboard.writeText(`${window.location.origin}${data.accept_path}`)
        setMessage('Novo link gerado e copiado.')
      } else {
        setMessage('Novo link gerado.')
      }
    },
    onError: (err) =>
      setError(getApiErrorMessage(err, 'Nao foi possivel gerar um novo link.')),
  })

  const copyPublicInvitationLink = async (invitation: PublicInvitation) => {
    if (!invitation.accept_path) {
      setMessage('')
      setError('Este link publico nao esta mais ativo.')
      return
    }
    await navigator.clipboard.writeText(
      `${window.location.origin}${invitation.accept_path}`
    )
    setMessage('Link publico copiado.')
    setError('')
  }

  const copyInvitationLink = async (invitation: Invitation) => {
    if (!invitation.accept_path) {
      setMessage('')
      setError('Este convite nao possui link armazenado. Gere um novo link.')
      return
    }
    await navigator.clipboard.writeText(
      `${window.location.origin}${invitation.accept_path}`
    )
    setMessage('Link copiado.')
    setError('')
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black text-white flex items-center gap-3">
          <div className="w-9 h-9 bg-violet-600 rounded-xl flex items-center justify-center text-white">
            <MailPlus className="w-5 h-5" />
          </div>
          Convites
        </h1>
        <p className="text-gray-400 text-sm mt-0.5">
          A entrada na plataforma ocorre por convite e ativa apenas a jornada escolhida.
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
        <Card className="xl:col-span-1">
          <h2 className="text-white font-bold mb-4">Novo convite</h2>
          <div className="grid grid-cols-2 gap-2 mb-4">
            <button
              type="button"
              onClick={() => {
                setMode('INDIVIDUAL')
                setMessage('')
                setError('')
              }}
              className={`rounded-xl px-3 py-2 text-xs font-semibold border transition-colors ${
                mode === 'INDIVIDUAL'
                  ? 'bg-violet-600 border-violet-500 text-white'
                  : 'bg-gray-950 border-gray-800 text-gray-400 hover:text-white'
              }`}
            >
              <MailPlus className="w-3.5 h-3.5 inline mr-1" />
              Individual
            </button>
            <button
              type="button"
              onClick={() => {
                setMode('PUBLIC')
                setMessage('')
                setError('')
              }}
              className={`rounded-xl px-3 py-2 text-xs font-semibold border transition-colors ${
                mode === 'PUBLIC'
                  ? 'bg-violet-600 border-violet-500 text-white'
                  : 'bg-gray-950 border-gray-800 text-gray-400 hover:text-white'
              }`}
            >
              <Link2 className="w-3.5 h-3.5 inline mr-1" />
              Link publico
            </button>
          </div>
          <div className="space-y-4">
            {mode === 'INDIVIDUAL' ? (
              <Input
                label="E-mail"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            ) : (
              <>
                <Input
                  label="Nome do link (opcional)"
                  placeholder="Ex: Rede de profissionais 2026"
                  value={label}
                  onChange={(e) => setLabel(e.target.value)}
                />
                <div className="grid grid-cols-2 gap-3">
                  <Input
                    label="Limite de usos"
                    type="number"
                    min={1}
                    placeholder="Ilimitado"
                    value={maxUses}
                    onChange={(e) => setMaxUses(e.target.value)}
                  />
                  <Input
                    label="Validade (dias)"
                    type="number"
                    min={1}
                    max={365}
                    value={publicExpiresInDays}
                    onChange={(e) => setPublicExpiresInDays(Number(e.target.value))}
                  />
                </div>
              </>
            )}
            <div>
              <label className="block text-xs font-semibold text-gray-400 mb-1.5">
                Jornada
              </label>
              <select
                className="w-full bg-gray-950 border border-gray-800 rounded-xl px-3 py-2.5 text-sm text-white"
                value={journeyType}
                onChange={(e) => {
                  const next = e.target.value as JourneyType
                  setJourneyType(next)
                  setLocationId('')
                  setMissionId('')
                  setPurpose('GLOBAL_REGISTRATION')
                }}
              >
                <option value="PROFESSIONALS">Rede de Profissionais</option>
                <option value="LOCATIONS">Rede de Locais</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-400 mb-1.5">
                Finalidade do convite
              </label>
              <select
                className="w-full bg-gray-950 border border-gray-800 rounded-xl px-3 py-2.5 text-sm text-white"
                value={purpose}
                onChange={(e) => {
                  setPurpose(e.target.value as InvitationPurpose)
                  setMissionId('')
                }}
              >
                <option value="GLOBAL_REGISTRATION">Cadastro global</option>
                {journeyType === 'PROFESSIONALS' && (
                  <option value="PROFESSIONAL_NETWORK">Rede de profissionais</option>
                )}
                {journeyType === 'LOCATIONS' && (
                  <option value="LOCATION_REPRESENTATIVE">
                    Representante de local
                  </option>
                )}
                {journeyType === 'PROFESSIONALS' && (
                  <option value="MISSION_PARTICIPANT">Participante de missao</option>
                )}
              </select>
            </div>

            {purpose === 'MISSION_PARTICIPANT' && (
              <div>
                <label className="block text-xs font-semibold text-gray-400 mb-1.5">
                  Missao
                </label>
                <select
                  className="w-full bg-gray-950 border border-gray-800 rounded-xl px-3 py-2.5 text-sm text-white"
                  value={missionId}
                  onChange={(e) => setMissionId(e.target.value)}
                >
                  <option value="">Selecione...</option>
                  {missions.data?.map((mission) => (
                    <option key={mission.id} value={mission.id}>
                      {mission.title} - {mission.city}/{mission.state}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold text-gray-400 mb-1.5">
                Dados solicitados no cadastro
              </label>
              <div className="grid grid-cols-2 gap-2">
                {DATA_CATEGORIES.map((category) => (
                  <label
                    key={category.value}
                    className="flex items-center gap-2 rounded-lg border border-gray-800 bg-gray-950 px-2.5 py-2 text-xs text-gray-300"
                  >
                    <input
                      type="checkbox"
                      className="accent-violet-600"
                      checked={requiredCategories.includes(category.value)}
                      onChange={(e) =>
                        setRequiredCategories((current) =>
                          e.target.checked
                            ? [...current, category.value]
                            : current.filter((item) => item !== category.value)
                        )
                      }
                    />
                    {category.label}
                  </label>
                ))}
              </div>
            </div>

            {journeyType === 'LOCATIONS' ? (
              <div>
                <label className="block text-xs font-semibold text-gray-400 mb-1.5">
                  Escola / Local
                </label>
                <select
                  className="w-full bg-gray-950 border border-gray-800 rounded-xl px-3 py-2.5 text-sm text-white"
                  value={locationId}
                  onChange={(e) => setLocationId(e.target.value)}
                >
                  <option value="">Selecione...</option>
                  {locations.data?.map((location) => (
                    <option key={location.id} value={location.id}>
                      {location.name} - {location.city}/{location.state}
                    </option>
                  ))}
                </select>
              </div>
            ) : isAdmin && purpose !== 'MISSION_PARTICIPANT' ? (
              <div>
                <label className="block text-xs font-semibold text-gray-400 mb-1.5">
                  Organizacao (opcional)
                </label>
                <select
                  className="w-full bg-gray-950 border border-gray-800 rounded-xl px-3 py-2.5 text-sm text-white"
                  value={organizationId}
                  onChange={(e) => setOrganizationId(e.target.value)}
                >
                  <option value="">Sem organizacao</option>
                  {organizations.data?.map((organization) => (
                    <option key={organization.id} value={organization.id}>
                      {organization.name}
                    </option>
                  ))}
                </select>
              </div>
            ) : (
              <p className="text-xs text-gray-500">
                {purpose === 'MISSION_PARTICIPANT'
                  ? 'A organizacao sera derivada da missao selecionada.'
                  : 'O convite sera vinculado automaticamente a sua organizacao.'}
              </p>
            )}

            <Button
              className="w-full"
              loading={mode === 'PUBLIC' ? createPublic.isPending : create.isPending}
              disabled={
                (mode === 'INDIVIDUAL' ? !email : false) ||
                (journeyType === 'LOCATIONS' && !locationId) ||
                (purpose === 'MISSION_PARTICIPANT' && !missionId)
              }
              onClick={() => {
                setMessage('')
                setError('')
                setCreated(null)
                setCreatedPublic(null)
                if (mode === 'PUBLIC') {
                  createPublic.mutate()
                } else {
                  create.mutate()
                }
              }}
            >
              {mode === 'PUBLIC' ? 'Criar link publico' : 'Criar convite'}
            </Button>
          </div>

          {created?.token && (
            <div className="mt-5 rounded-xl border border-violet-600/30 bg-violet-600/10 p-3">
              <p className="text-xs text-violet-200">
                Link de aceite (valido ate{' '}
                {new Date(created.expires_at).toLocaleDateString('pt-BR')}):
              </p>
              <p className="text-[11px] text-violet-100 break-all mt-1">
                {window.location.origin}/convite/{created.token}
              </p>
              <Button
                size="sm"
                variant="secondary"
                className="mt-3"
                onClick={() => copyInvitationLink(created)}
              >
                <Copy className="w-3.5 h-3.5 mr-1" />
                Copiar link
              </Button>
            </div>
          )}

          {createdPublic?.token && (
            <div className="mt-5 rounded-xl border border-emerald-600/30 bg-emerald-600/10 p-3">
              <p className="text-xs text-emerald-200">
                Link publico reutilizavel (valido ate{' '}
                {new Date(createdPublic.expires_at).toLocaleDateString('pt-BR')}
                {createdPublic.max_uses
                  ? ` - limite de ${createdPublic.max_uses} usos`
                  : ' - usos ilimitados'}
                ):
              </p>
              <p className="text-[11px] text-emerald-100 break-all mt-1">
                {window.location.origin}
                {createdPublic.accept_path}
              </p>
              <Button
                size="sm"
                variant="secondary"
                className="mt-3"
                onClick={() => copyPublicInvitationLink(createdPublic)}
              >
                <Copy className="w-3.5 h-3.5 mr-1" />
                Copiar link publico
              </Button>
            </div>
          )}
        </Card>

        <Card className="xl:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-white font-bold flex items-center gap-2">
              <Link2 className="w-4 h-4 text-emerald-400" />
              Links publicos reutilizaveis
            </h2>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                invitations.refetch()
                publicInvitations.refetch()
              }}
              loading={invitations.isFetching || publicInvitations.isFetching}
            >
              <RefreshCw className="w-3.5 h-3.5 mr-1" />
              Atualizar
            </Button>
          </div>
          {publicInvitations.isLoading ? (
            <div className="flex justify-center py-6">
              <div className="animate-spin w-7 h-7 border-2 border-emerald-600 border-t-transparent rounded-full" />
            </div>
          ) : !publicInvitations.data?.length ? (
            <p className="text-gray-500 text-sm mb-6">Nenhum link publico criado.</p>
          ) : (
            <ul className="divide-y divide-gray-800 mb-6">
              {publicInvitations.data.map((invitation) => (
                <li
                  key={invitation.id}
                  className="py-3 flex flex-col md:flex-row md:items-center gap-2"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-white truncate flex items-center gap-2">
                      {invitation.label || 'Link publico'}
                      <Users className="w-3.5 h-3.5 text-emerald-400" />
                      <span className="text-[10px] text-gray-500 font-normal">
                        {invitation.uses_count} uso(s)
                        {invitation.max_uses ? ` de ${invitation.max_uses}` : ' - ilimitado'}
                      </span>
                    </p>
                    <p className="text-xs text-gray-500">
                      {PURPOSE_LABELS[invitation.purpose] || invitation.journey_type}
                      {invitation.location_name ? ` - ${invitation.location_name}` : ''}
                      {invitation.organization_name ? ` - ${invitation.organization_name}` : ''}
                    </p>
                    <p className="text-[10px] text-gray-600 mt-0.5">
                      Expira em {new Date(invitation.expires_at).toLocaleDateString('pt-BR')}
                    </p>
                    {invitation.status === 'ACTIVE' && invitation.accept_path && (
                      <p className="text-[10px] text-emerald-300/80 break-all mt-1">
                        {window.location.origin}
                        {invitation.accept_path}
                      </p>
                    )}
                  </div>
                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                      invitation.status === 'ACTIVE'
                        ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
                        : 'text-gray-400 bg-gray-800 border-gray-700'
                    }`}
                  >
                    {invitation.status}
                  </span>
                  {invitation.status === 'ACTIVE' && (
                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => copyPublicInvitationLink(invitation)}
                      >
                        <Copy className="w-3.5 h-3.5 mr-1" />
                        Copiar
                      </Button>
                      <Button
                        size="sm"
                        variant="secondary"
                        loading={revokePublic.isPending}
                        onClick={() => revokePublic.mutate(invitation.id)}
                      >
                        <XCircle className="w-3.5 h-3.5 mr-1" />
                        Revogar
                      </Button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}

          <div className="flex items-center justify-between mb-4 pt-4 border-t border-gray-800">
            <h2 className="text-white font-bold">Convites individuais</h2>
          </div>
          {invitations.isLoading ? (
            <div className="flex justify-center py-10">
              <div className="animate-spin w-8 h-8 border-2 border-violet-600 border-t-transparent rounded-full" />
            </div>
          ) : !invitations.data?.length ? (
            <p className="text-gray-500 text-sm">Nenhum convite emitido.</p>
          ) : (
            <ul className="divide-y divide-gray-800">
              {invitations.data.map((invitation) => (
                <li
                  key={invitation.id}
                  className="py-3 flex flex-col md:flex-row md:items-center gap-2"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-white truncate">{invitation.email}</p>
                    <p className="text-xs text-gray-500">
                      {PURPOSE_LABELS[invitation.purpose] || invitation.journey_type}
                      {invitation.location_name ? ` - ${invitation.location_name}` : ''}
                      {invitation.organization_name ? ` - ${invitation.organization_name}` : ''}
                    </p>
                    <p className="text-[10px] text-gray-600 mt-0.5">
                      Expira em {new Date(invitation.expires_at).toLocaleDateString('pt-BR')}
                      {invitation.token_prefix ? ` - ${invitation.token_prefix}` : ''}
                    </p>
                    {invitation.status === 'PENDING' && invitation.accept_path && (
                      <p className="text-[10px] text-violet-300/80 break-all mt-1">
                        {window.location.origin}
                        {invitation.accept_path}
                      </p>
                    )}
                  </div>
                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                      invitation.status === 'PENDING'
                        ? 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20'
                        : invitation.status === 'ACCEPTED'
                          ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
                          : 'text-gray-400 bg-gray-800 border-gray-700'
                    }`}
                  >
                    {invitation.status}
                  </span>
                  {invitation.status === 'PENDING' && (
                    <div className="flex items-center gap-2">
                      {invitation.accept_path ? (
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => copyInvitationLink(invitation)}
                        >
                          <Copy className="w-3.5 h-3.5 mr-1" />
                          Copiar link
                        </Button>
                      ) : (
                        <Button
                          size="sm"
                          variant="secondary"
                          loading={regenerate.isPending}
                          onClick={() => regenerate.mutate(invitation.id)}
                        >
                          <RefreshCw className="w-3.5 h-3.5 mr-1" />
                          Gerar link
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="secondary"
                        loading={revoke.isPending}
                        onClick={() => revoke.mutate(invitation.id)}
                      >
                        <XCircle className="w-3.5 h-3.5 mr-1" />
                        Revogar
                      </Button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}
