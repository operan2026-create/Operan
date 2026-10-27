import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  BadgeCheck,
  Building2,
  Search,
  ShieldCheck,
  UserRound,
  Users,
} from 'lucide-react'
import api from '../api/client'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { useAuth } from '../hooks/useAuth'
import { getApiErrorMessage } from '../lib/errors'
import type {
  ParticipantDetail,
  ParticipantSummary,
  ParticipantValidation,
  ParticipantValidationPayload,
  ParticipantValidationScope,
  ParticipantValidationStatus,
} from '../types'

const STATUS_STYLES: Record<ParticipantValidationStatus, string> = {
  VALIDATED: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
  PENDING: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20',
  REJECTED: 'text-red-400 bg-red-500/10 border-red-500/20',
  SUSPENDED: 'text-gray-400 bg-gray-800 border-gray-700',
  UPDATE_REQUIRED: 'text-orange-400 bg-orange-500/10 border-orange-500/20',
}

const SCOPES: ParticipantValidationScope[] = [
  'GLOBAL',
  'PROFILE',
  'DOCUMENTS',
  'BANK',
  'FAMILY',
  'QUALIFICATIONS',
]

export function ParticipantsPage() {
  const { isAdmin } = useAuth()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState('')
  const [scope, setScope] = useState<ParticipantValidationScope>('PROFILE')
  const [statusValue, setStatusValue] =
    useState<ParticipantValidationStatus>('VALIDATED')
  const [notes, setNotes] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const participants = useQuery({
    queryKey: ['participants'],
    queryFn: () =>
      api
        .get<ParticipantSummary[]>('/participants', { params: { limit: 200 } })
        .then((r) => r.data),
  })

  const detail = useQuery({
    queryKey: ['participant', selectedId],
    queryFn: () =>
      api
        .get<ParticipantDetail>(`/participants/${selectedId}`)
        .then((r) => r.data),
    enabled: Boolean(selectedId),
    retry: false,
  })

  const validations = useQuery({
    queryKey: ['participant-validations', selectedId],
    queryFn: () =>
      api
        .get<ParticipantValidation[]>(`/participants/${selectedId}/validations`)
        .then((r) => r.data),
    enabled: Boolean(selectedId) && isAdmin,
  })

  const createValidation = useMutation({
    mutationFn: (payload: ParticipantValidationPayload) =>
      api
        .post<ParticipantValidation>(
          `/participants/${selectedId}/validations`,
          payload
        )
        .then((r) => r.data),
    onSuccess: () => {
      setNotes('')
      setMessage('Validacao registrada.')
      setError('')
      queryClient.invalidateQueries({ queryKey: ['participants'] })
      queryClient.invalidateQueries({ queryKey: ['participant', selectedId] })
      queryClient.invalidateQueries({
        queryKey: ['participant-validations', selectedId],
      })
    },
    onError: (err) =>
      setError(getApiErrorMessage(err, 'Nao foi possivel registrar a validacao.')),
  })

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase()
    if (!term) return participants.data ?? []
    return (participants.data ?? []).filter((participant) =>
      [participant.full_name, participant.public_id, participant.city, participant.state]
        .filter(Boolean)
        .some((value) => value.toLowerCase().includes(term))
    )
  }, [participants.data, search])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black text-white flex items-center gap-3">
          <div className="w-9 h-9 bg-violet-600 rounded-xl flex items-center justify-center text-white">
            <Users className="w-5 h-5" />
          </div>
          Participantes
        </h1>
        <p className="text-gray-400 text-sm mt-0.5">
          {isAdmin
            ? 'Diretorio global de participantes e validacao cadastral.'
            : 'Participantes vinculados aos seus contratos e missoes.'}
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
          <div className="relative mb-4">
            <Search className="w-4 h-4 text-gray-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              className="w-full bg-gray-950 border border-gray-800 rounded-xl pl-9 pr-3 py-2.5 text-sm text-white"
              placeholder="Buscar por nome, ID ou cidade"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          {participants.isLoading ? (
            <div className="flex justify-center py-8">
              <div className="animate-spin w-7 h-7 border-2 border-violet-600 border-t-transparent rounded-full" />
            </div>
          ) : !filtered.length ? (
            <p className="text-gray-500 text-sm">Nenhum participante encontrado.</p>
          ) : (
            <ul className="divide-y divide-gray-800 max-h-[70vh] overflow-y-auto">
              {filtered.map((participant) => (
                <li key={participant.user_id}>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedId(participant.user_id)
                      setMessage('')
                      setError('')
                    }}
                    className={`w-full text-left py-3 px-2 rounded-lg transition-colors ${
                      selectedId === participant.user_id
                        ? 'bg-violet-600/10'
                        : 'hover:bg-gray-800/50'
                    }`}
                  >
                    <p className="text-sm text-white font-semibold truncate">
                      {participant.full_name}
                    </p>
                    <p className="text-xs text-gray-500">
                      {participant.public_id} - {participant.city}/{participant.state}
                    </p>
                    <span
                      className={`inline-block mt-1 text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                        STATUS_STYLES[participant.cadastral_status]
                      }`}
                    >
                      {participant.cadastral_status}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="xl:col-span-2">
          {!selectedId ? (
            <div className="text-center py-16">
              <UserRound className="w-10 h-10 text-gray-700 mx-auto mb-3" />
              <p className="text-gray-500 text-sm">
                Selecione um participante para ver o resumo operacional.
              </p>
            </div>
          ) : detail.isLoading ? (
            <div className="flex justify-center py-16">
              <div className="animate-spin w-8 h-8 border-2 border-violet-600 border-t-transparent rounded-full" />
            </div>
          ) : detail.isError || !detail.data ? (
            <p className="text-red-300 text-sm py-8">
              Nao foi possivel acessar este participante.
            </p>
          ) : (
            <div className="space-y-5">
              <div className="flex items-start gap-4">
                <div className="w-14 h-14 rounded-2xl bg-violet-600/20 text-violet-300 flex items-center justify-center font-black text-xl">
                  {detail.data.full_name.slice(0, 1).toUpperCase()}
                </div>
                <div className="min-w-0 flex-1">
                  <h2 className="text-xl font-black text-white truncate">
                    {detail.data.full_name}
                  </h2>
                  {detail.data.social_name && (
                    <p className="text-sm text-gray-400">{detail.data.social_name}</p>
                  )}
                  <p className="text-xs text-gray-500 mt-1">
                    {detail.data.public_id}
                    {detail.data.cpf_masked ? ` - ${detail.data.cpf_masked}` : ''}
                    {detail.data.phone_masked ? ` - ${detail.data.phone_masked}` : ''}
                  </p>
                  <div className="flex flex-wrap gap-2 mt-2">
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                        STATUS_STYLES[detail.data.cadastral_status]
                      }`}
                    >
                      {detail.data.cadastral_status}
                    </span>
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full border border-gray-700 text-gray-400">
                      {detail.data.profile_completed ? 'PERFIL COMPLETO' : 'PERFIL INCOMPLETO'}
                    </span>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="rounded-xl border border-gray-800 bg-gray-950 p-3">
                  <p className="text-xs font-semibold text-gray-400 mb-2 flex items-center gap-1.5">
                    <Building2 className="w-3.5 h-3.5" />
                    Organizacoes vinculadas
                  </p>
                  {detail.data.organizations.length ? (
                    <ul className="space-y-1.5">
                      {detail.data.organizations.map((organization) => (
                        <li key={organization.organization_id} className="text-xs text-gray-300">
                          {organization.organization_name || organization.organization_id}
                          <span className="text-gray-600"> - {organization.status}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-xs text-gray-600">Nenhum vinculo ativo.</p>
                  )}
                </div>
                <div className="rounded-xl border border-gray-800 bg-gray-950 p-3">
                  <p className="text-xs font-semibold text-gray-400 mb-2 flex items-center gap-1.5">
                    <BadgeCheck className="w-3.5 h-3.5" />
                    Jornadas e qualificacoes
                  </p>
                  <p className="text-xs text-gray-300">
                    {detail.data.journeys.map((journey) => journey.journey_type).join(', ') ||
                      'Sem jornada ativa'}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {detail.data.qualifications.length} qualificacao(oes)
                  </p>
                </div>
              </div>

              {isAdmin && (
                <div className="rounded-xl border border-gray-800 bg-gray-950 p-4">
                  <p className="text-sm font-bold text-white flex items-center gap-2 mb-3">
                    <ShieldCheck className="w-4 h-4 text-violet-400" />
                    Validacao cadastral
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-gray-400 mb-1.5">
                        Escopo
                      </label>
                      <select
                        className="w-full bg-gray-950 border border-gray-800 rounded-xl px-3 py-2.5 text-sm text-white"
                        value={scope}
                        onChange={(e) =>
                          setScope(e.target.value as ParticipantValidationScope)
                        }
                      >
                        {SCOPES.map((value) => (
                          <option key={value} value={value}>
                            {value}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-gray-400 mb-1.5">
                        Status
                      </label>
                      <select
                        className="w-full bg-gray-950 border border-gray-800 rounded-xl px-3 py-2.5 text-sm text-white"
                        value={statusValue}
                        onChange={(e) =>
                          setStatusValue(e.target.value as ParticipantValidationStatus)
                        }
                      >
                        {(
                          [
                            'VALIDATED',
                            'PENDING',
                            'UPDATE_REQUIRED',
                            'REJECTED',
                            'SUSPENDED',
                          ] as ParticipantValidationStatus[]
                        ).map((value) => (
                          <option key={value} value={value}>
                            {value}
                          </option>
                        ))}
                      </select>
                    </div>
                    <Input
                      label="Observacoes"
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                    />
                  </div>
                  <Button
                    className="mt-3"
                    loading={createValidation.isPending}
                    onClick={() => {
                      setMessage('')
                      setError('')
                      createValidation.mutate({
                        scope,
                        status: statusValue,
                        notes: notes || undefined,
                      })
                    }}
                  >
                    Registrar validacao
                  </Button>

                  {validations.data?.length ? (
                    <ul className="mt-4 space-y-2">
                      {validations.data.map((event) => (
                        <li
                          key={event.id}
                          className="rounded-lg border border-gray-800 px-3 py-2 text-xs"
                        >
                          <p className="text-gray-300">
                            {event.scope} - {event.status}
                            <span className="text-gray-600">
                              {' '}
                              por {event.reviewer_public_id || 'sistema'}
                            </span>
                          </p>
                          {event.notes && <p className="text-gray-500 mt-0.5">{event.notes}</p>}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              )}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
