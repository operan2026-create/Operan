import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  CheckCircle2,
  Circle,
  Clock,
  FileText,
  MapPin,
  School,
  Send,
  Upload,
  XCircle,
} from 'lucide-react'
import api from '../api/client'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { getApiErrorMessage } from '../lib/errors'
import { downloadDocument } from '../lib/download'
import type {
  DocumentItem,
  RepresentativeLink,
  WorkflowEvent,
} from '../types'

type SchoolDetail = {
  link: RepresentativeLink
  events: WorkflowEvent[]
  documents: DocumentItem[]
}

const STAGES = [
  { key: 'CAPTURE', label: 'Captacao', hint: 'Dados cadastrais da escola' },
  { key: 'DOCUMENTATION', label: 'Documentacao', hint: 'Documentos e comprovantes' },
  { key: 'INSPECTION', label: 'Vistoria', hint: 'Validacao presencial' },
  { key: 'RELEASE', label: 'Liberacao', hint: 'Decisao final OPERAN/cliente' },
] as const

export function RepresentativeSchoolsPage() {
  const queryClient = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [documentType, setDocumentType] = useState('SCHOOL_DOCUMENT')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const schools = useQuery({
    queryKey: ['representative-schools'],
    queryFn: () =>
      api.get<RepresentativeLink[]>('/representatives/schools').then((r) => r.data),
  })

  const activeId = selectedId ?? schools.data?.[0]?.location_id
  const detail = useQuery({
    queryKey: ['representative-school', activeId],
    queryFn: () =>
      api
        .get<SchoolDetail>(`/representatives/schools/${activeId}`)
        .then((r) => r.data),
    enabled: Boolean(activeId),
  })

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['representative-schools'] })
    queryClient.invalidateQueries({ queryKey: ['representative-school', activeId] })
  }

  const submitStage = useMutation({
    mutationFn: (stage: string) =>
      api.post(`/representatives/schools/${activeId}/submit/${stage}`),
    onSuccess: () => {
      setMessage('Etapa enviada para analise.')
      setError('')
      refresh()
    },
    onError: (err) => {
      setMessage('')
      setError(getApiErrorMessage(err, 'Nao foi possivel enviar a etapa.'))
    },
  })

  const upload = useMutation({
    mutationFn: (file: File) => {
      const data = new FormData()
      data.append('file', file)
      data.append('document_type', documentType)
      return api
        .post(`/representatives/schools/${activeId}/documents`, data, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        .then((r) => r.data)
    },
    onSuccess: () => {
      setMessage('Documento enviado.')
      setError('')
      refresh()
      if (fileRef.current) fileRef.current.value = ''
    },
    onError: (err) => {
      setMessage('')
      setError(getApiErrorMessage(err, 'Nao foi possivel enviar o documento.'))
    },
  })

  const latestEvent = (stage: string): WorkflowEvent | undefined =>
    detail.data?.events
      .filter((event) => event.stage === stage)
      .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))[0]

  if (schools.isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin w-8 h-8 border-2 border-violet-600 border-t-transparent rounded-full" />
      </div>
    )
  }

  if (!schools.data?.length) {
    return (
      <Card className="text-center py-16">
        <School className="w-12 h-12 text-gray-700 mx-auto mb-3" />
        <p className="text-white font-semibold">Nenhuma escola vinculada</p>
        <p className="text-gray-500 text-sm mt-1 max-w-md mx-auto">
          A escola deve convidar seu e-mail como representante. Ao aceitar o convite, o vinculo
          aparece aqui.
        </p>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black text-white flex items-center gap-3">
          <div className="w-9 h-9 bg-violet-600 rounded-xl flex items-center justify-center text-white">
            <School className="w-5 h-5" />
          </div>
          Minhas Escolas
        </h1>
        <p className="text-gray-400 text-sm mt-0.5">
          Captacao, documentacao e acompanhamento do workflow de liberacao.
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

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
        <Card className="xl:col-span-1">
          <h2 className="text-white font-bold mb-4">Vinculos ativos</h2>
          <div className="space-y-2">
            {schools.data.map((school) => (
              <button
                key={school.id}
                onClick={() => setSelectedId(school.location_id)}
                className={`w-full text-left rounded-xl border px-3 py-2.5 transition-colors ${
                  school.location_id === activeId
                    ? 'border-violet-600/40 bg-violet-600/10'
                    : 'border-gray-800 bg-gray-950 hover:border-gray-700'
                }`}
              >
                <p className="text-sm font-semibold text-white truncate">
                  {school.location_name || 'Escola'}
                </p>
                <p className="text-xs text-gray-500 flex items-center gap-1 mt-0.5">
                  <MapPin className="w-3 h-3" />
                  {school.city} / {school.state}
                </p>
                <p className="text-[10px] uppercase font-bold text-violet-400 mt-1">
                  {school.status}
                </p>
              </button>
            ))}
          </div>
        </Card>

        <div className="xl:col-span-3 space-y-6">
          {detail.isLoading ? (
            <Card>
              <div className="flex justify-center py-12">
                <div className="animate-spin w-8 h-8 border-2 border-violet-600 border-t-transparent rounded-full" />
              </div>
            </Card>
          ) : detail.data ? (
            <>
              <Card>
                <h2 className="text-white font-bold mb-4">Workflow de liberacao</h2>
                <div className="space-y-3">
                  {STAGES.map((stage, index) => {
                    const event = latestEvent(stage.key)
                    const canSubmit =
                      stage.key !== 'RELEASE' &&
                      (!event || event.status === 'REJECTED')
                    return (
                      <div
                        key={stage.key}
                        className="flex flex-col md:flex-row md:items-center gap-3 rounded-xl border border-gray-800 bg-gray-950 p-3"
                      >
                        <div className="flex items-center gap-3 flex-1">
                          {event?.status === 'APPROVED' ? (
                            <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                          ) : event?.status === 'SUBMITTED' ? (
                            <Clock className="w-5 h-5 text-yellow-400" />
                          ) : event?.status === 'REJECTED' ? (
                            <XCircle className="w-5 h-5 text-red-400" />
                          ) : (
                            <Circle className="w-5 h-5 text-gray-600" />
                          )}
                          <div>
                            <p className="text-sm font-semibold text-white">
                              {index + 1}. {stage.label}
                            </p>
                            <p className="text-xs text-gray-500">{stage.hint}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-gray-400">
                            {event?.status || 'NAO INICIADO'}
                          </span>
                          {canSubmit && (
                            <Button
                              size="sm"
                              variant="secondary"
                              loading={submitStage.isPending}
                              onClick={() => {
                                setMessage('')
                                setError('')
                                submitStage.mutate(stage.key)
                              }}
                            >
                              <Send className="w-3.5 h-3.5 mr-1" />
                              Enviar
                            </Button>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </Card>

              <Card>
                <h2 className="text-white font-bold mb-4">Documentos da escola</h2>
                <div className="flex flex-wrap items-end gap-3 mb-4">
                  <div>
                    <label className="block text-xs font-semibold text-gray-400 mb-1.5">
                      Tipo
                    </label>
                    <select
                      className="bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-sm text-white"
                      value={documentType}
                      onChange={(e) => setDocumentType(e.target.value)}
                    >
                      {['SCHOOL_DOCUMENT', 'INSPECTION_REPORT', 'PROOF_OF_ADDRESS', 'OTHER'].map(
                        (type) => (
                          <option key={type} value={type}>
                            {type}
                          </option>
                        )
                      )}
                    </select>
                  </div>
                  <input
                    ref={fileRef}
                    type="file"
                    accept="application/pdf,image/jpeg,image/png"
                    className="text-sm text-gray-400"
                  />
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
                    Enviar
                  </Button>
                </div>
                {detail.data.documents.length === 0 ? (
                  <p className="text-gray-500 text-sm">Nenhum documento enviado.</p>
                ) : (
                  <ul className="divide-y divide-gray-800">
                    {detail.data.documents.map((doc) => (
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
                )}
              </Card>
            </>
          ) : (
            <Card>
              <p className="text-gray-500 text-sm">Selecione uma escola.</p>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
