import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Circle, Clock, School, X, XCircle } from 'lucide-react'
import api from '../api/client'
import { Button } from './ui/Button'
import { Input } from './ui/Input'
import { getApiErrorMessage } from '../lib/errors'
import type { Location, RepresentativeLink, WorkflowEvent } from '../types'

const STAGES = [
  { key: 'CAPTURE', label: 'Captacao' },
  { key: 'DOCUMENTATION', label: 'Documentacao' },
  { key: 'INSPECTION', label: 'Vistoria' },
  { key: 'RELEASE', label: 'Liberacao final' },
] as const

type Props = {
  location: Location
  onClose: () => void
}

export function LocationWorkflowModal({ location, onClose }: Props) {
  const queryClient = useQueryClient()
  const [notes, setNotes] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const links = useQuery({
    queryKey: ['location-representatives', location.id],
    queryFn: () =>
      api
        .get<RepresentativeLink[]>(`/representatives/locations/${location.id}/links`)
        .then((r) => r.data),
  })

  const events = useQuery({
    queryKey: ['location-workflow-events', location.id],
    queryFn: () =>
      api
        .get<WorkflowEvent[]>(`/representatives/schools/${location.id}/events`)
        .then((r) => r.data),
  })

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['location-representatives', location.id] })
    queryClient.invalidateQueries({ queryKey: ['location-workflow-events', location.id] })
    queryClient.invalidateQueries({ queryKey: ['locations'] })
  }

  const decide = useMutation({
    mutationFn: ({ stage, approve }: { stage: string; approve: boolean }) =>
      api.post(`/representatives/locations/${location.id}/stages/${stage}/decision`, {
        approve,
        notes: notes || undefined,
      }),
    onSuccess: () => {
      setMessage('Etapa decidida.')
      setError('')
      setNotes('')
      refresh()
    },
    onError: (err) => {
      setMessage('')
      setError(getApiErrorMessage(err, 'Nao foi possivel decidir a etapa.'))
    },
  })

  const updateLink = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.patch(`/representatives/links/${id}`, { status }),
    onSuccess: () => {
      setMessage('Vinculo atualizado.')
      setError('')
      refresh()
    },
    onError: (err) => {
      setMessage('')
      setError(getApiErrorMessage(err, 'Nao foi possivel atualizar o vinculo.'))
    },
  })

  const latestEvent = (stage: string) =>
    events.data
      ?.filter((event) => event.stage === stage)
      .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))[0]

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
      <div className="bg-gray-900 border border-gray-800 rounded-2xl w-full max-w-2xl p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <h2 className="text-xl font-bold text-white">{location.name}</h2>
            <p className="text-sm text-gray-400 mt-0.5">
              Representantes e workflow de liberacao
            </p>
          </div>
          <button className="text-gray-500 hover:text-white" onClick={onClose}>
            <X className="w-5 h-5" />
          </button>
        </div>

        {(message || error) && (
          <div
            className={`rounded-xl px-4 py-3 text-sm border mb-4 ${
              error
                ? 'bg-red-500/10 border-red-500/30 text-red-300'
                : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
            }`}
          >
            {error || message}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="rounded-xl border border-gray-800 p-4">
            <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
              <School className="w-4 h-4 text-violet-400" />
              Representantes
            </h3>
            {links.isLoading ? (
              <p className="text-xs text-gray-500">Carregando...</p>
            ) : !links.data?.length ? (
              <p className="text-xs text-gray-500">Nenhum representante vinculado.</p>
            ) : (
              <ul className="space-y-2">
                {links.data.map((link) => (
                  <li
                    key={link.id}
                    className="flex items-center justify-between gap-2 rounded-lg bg-gray-950 px-3 py-2"
                  >
                    <div>
                      <p className="text-xs font-semibold text-white">{link.status}</p>
                      <p className="text-[10px] text-gray-500">
                        Desde{' '}
                        {link.started_at
                          ? new Date(link.started_at).toLocaleDateString('pt-BR')
                          : '-'}
                      </p>
                    </div>
                    <Button
                      size="sm"
                      variant="secondary"
                      loading={updateLink.isPending}
                      onClick={() =>
                        updateLink.mutate({
                          id: link.id,
                          status: link.status === 'ACTIVE' ? 'SUSPENDED' : 'ACTIVE',
                        })
                      }
                    >
                      {link.status === 'ACTIVE' ? 'Suspender' : 'Reativar'}
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="rounded-xl border border-gray-800 p-4">
            <h3 className="text-sm font-bold text-white mb-3">Workflow</h3>
            {events.isLoading ? (
              <p className="text-xs text-gray-500">Carregando...</p>
            ) : (
              <ul className="space-y-2">
                {STAGES.map((stage) => {
                  const event = latestEvent(stage.key)
                  return (
                    <li
                      key={stage.key}
                      className="rounded-lg bg-gray-950 px-3 py-2"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-semibold text-white flex items-center gap-1.5">
                          {event?.status === 'APPROVED' ? (
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                          ) : event?.status === 'SUBMITTED' ? (
                            <Clock className="w-3.5 h-3.5 text-yellow-400" />
                          ) : event?.status === 'REJECTED' ? (
                            <XCircle className="w-3.5 h-3.5 text-red-400" />
                          ) : (
                            <Circle className="w-3.5 h-3.5 text-gray-600" />
                          )}
                          {stage.label}
                        </span>
                        <span className="text-[10px] font-bold text-gray-500">
                          {event?.status || 'NAO INICIADO'}
                        </span>
                      </div>
                      {event?.status === 'SUBMITTED' && (
                        <div className="flex items-center gap-2 mt-2">
                          <Button
                            size="sm"
                            loading={decide.isPending}
                            onClick={() => decide.mutate({ stage: stage.key, approve: true })}
                          >
                            Aprovar
                          </Button>
                          <Button
                            size="sm"
                            variant="secondary"
                            loading={decide.isPending}
                            onClick={() => decide.mutate({ stage: stage.key, approve: false })}
                          >
                            Recusar
                          </Button>
                        </div>
                      )}
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
        </div>

        <div className="mt-4">
          <Input
            label="Observacao da decisao (opcional)"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </div>
      </div>
    </div>
  )
}
