import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Target, Plus, CheckCircle2, MapPin, ListChecks, ShieldAlert, UserPlus, Award, X } from 'lucide-react'
import api from '../api/client'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { useArea } from '../hooks/useArea'
import { useAuth } from '../hooks/useAuth'
import { PROFESSIONAL_FUNCTIONS, professionalFunctionLabel } from '../lib/professionalFunctions'
import type { Mission, MissionApplication, MissionInvitation, Professional, Location } from '../types'

const typeBadges = {
  VISTORIA: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  CAPTACAO: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  CONFIRMACAO: 'bg-green-500/20 text-green-400 border-green-500/30',
  RECERTIFICACAO: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  APOIO_OPERACIONAL: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
}

export function MissionsPage() {
  const queryClient = useQueryClient()
  const area = useArea()
  const { user } = useAuth()
  const canManage = area === 'admin' || user?.roles?.includes('CLIENT_ADMIN')
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [missionType, setMissionType] = useState('VISTORIA')
  const [requiredFunction, setRequiredFunction] = useState('')
  const [locationId, setLocationId] = useState('')
  const [city, setCity] = useState('')
  const [state, setState] = useState('DF')
  const [rewardAmount, setRewardAmount] = useState(180)
  const [selectedMission, setSelectedMission] = useState<Mission | null>(null)
  const [decisionNotes, setDecisionNotes] = useState('')
  const [inviteMission, setInviteMission] = useState<Mission | null>(null)
  const [inviteState, setInviteState] = useState('')
  const [inviteCity, setInviteCity] = useState('')
  const [inviteFunction, setInviteFunction] = useState('')
  const [inviteMessage, setInviteMessage] = useState('')
  const [inviteFeedback, setInviteFeedback] = useState('')
  const [inviteError, setInviteError] = useState('')

  const { data: missions, isLoading } = useQuery({
    queryKey: ['missions', area],
    queryFn: () => api.get<Mission[]>('/missions').then(r => r.data),
  })

  const { data: locations } = useQuery({
    queryKey: ['locations', area],
    queryFn: () => api.get<Location[]>('/locations').then(r => r.data),
  })

  const { data: applications, isLoading: applicationsLoading } = useQuery({
    queryKey: ['mission-applications', selectedMission?.id],
    queryFn: () =>
      api
        .get<MissionApplication[]>(`/missions/${selectedMission?.id}/applications`)
        .then(r => r.data),
    enabled: Boolean(selectedMission?.id && canManage),
  })

  const { data: inviteProfessionals, isLoading: inviteProfessionalsLoading } = useQuery({
    queryKey: ['invite-professionals', inviteMission?.id, inviteState, inviteCity, inviteFunction],
    queryFn: () =>
      api
        .get<Professional[]>('/professionals', {
          params: {
            state: inviteState || undefined,
            city: inviteCity || undefined,
            function: inviteFunction || undefined,
          },
        })
        .then(r => r.data),
    enabled: Boolean(inviteMission?.id && canManage),
  })

  const { data: missionInvitations } = useQuery({
    queryKey: ['mission-invitations', inviteMission?.id],
    queryFn: () =>
      api
        .get<MissionInvitation[]>(`/missions/${inviteMission?.id}/invitations`)
        .then(r => r.data),
    enabled: Boolean(inviteMission?.id && canManage),
  })

  const inviteMutation = useMutation({
    mutationFn: (userId: string) =>
      api.post(`/missions/${inviteMission?.id}/invitations`, {
        user_ids: [userId],
        message: inviteMessage || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mission-invitations', inviteMission?.id] })
      setInviteFeedback('Convite enviado. O profissional vera na area de missoes.')
      setInviteError('')
    },
    onError: (error: any) => {
      setInviteError(
        error?.response?.data?.detail || 'Nao foi possivel enviar o convite.'
      )
      setInviteFeedback('')
    },
  })

  const openInviteModal = (mission: Mission) => {
    setInviteMission(mission)
    setInviteState(mission.state || '')
    setInviteCity(mission.city || '')
    setInviteFunction(mission.required_function || '')
    setInviteMessage('')
    setInviteFeedback('')
    setInviteError('')
  }

  const invitedUserIds = new Set(
    (missionInvitations || [])
      .filter(invite => invite.status === 'INVITED' || invite.status === 'ACCEPTED')
      .map(invite => invite.user_id)
  )

  const createMutation = useMutation({
    mutationFn: (newMission: any) => api.post('/missions', newMission),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['missions', area] })
      setIsModalOpen(false)
      setTitle('')
      setCity('')
    },
  })

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.patch(`/missions/${id}/status`, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['missions', area] })
    },
  })

  const decideMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: 'SELECTED' | 'REJECTED' }) =>
      api.patch(`/missions/applications/${id}/decision`, {
        status,
        notes: decisionNotes || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mission-applications', selectedMission?.id] })
      queryClient.invalidateQueries({ queryKey: ['missions', area] })
      setDecisionNotes('')
    },
  })

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate({
      title,
      mission_type: missionType,
      required_function: requiredFunction || undefined,
      location_id: locationId || undefined,
      city,
      state,
      reward_amount: Number(rewardAmount),
      status: 'OPEN',
      checklist: [
        { item: 'Validar acessibilidade física', done: false },
        { item: 'Contar carteiras por sala', done: false },
        { item: 'Registrar evidências fotográficas', done: false },
      ],
    })
  }

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Target className="w-7 h-7 text-violet-400" />
            Missions — Motor Operacional Territorial
          </h1>
          <p className="text-gray-400 mt-1">
            Despache vistorias, captações de novos prédios e reconfirmações pré-operação com checklists e remuneração
          </p>
        </div>
        {canManage && (
          <Button onClick={() => setIsModalOpen(true)}>
            <Plus className="w-4 h-4 mr-2" /> Despachar Nova Missão
          </Button>
        )}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <div className="animate-spin w-8 h-8 border-2 border-violet-600 border-t-transparent rounded-full" />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {missions?.map(m => (
            <Card key={m.id} className="flex flex-col justify-between border border-gray-800 hover:border-violet-600/40 transition-all">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className={`text-xs font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full border ${typeBadges[m.mission_type] || 'text-gray-400'}`}>
                    {m.mission_type}
                  </span>
                  <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                    m.status === 'COMPLETED' ? 'bg-green-500/20 text-green-400' :
                    m.status === 'IN_PROGRESS' ? 'bg-yellow-500/20 text-yellow-400' :
                    m.status === 'CANCELLED' ? 'bg-red-500/20 text-red-400' :
                    'bg-gray-800 text-gray-300'
                  }`}>
                    {m.status === 'OPEN' ? 'Aberta na Rede' :
                     m.status === 'ASSIGNED' ? 'Atribuída' :
                     m.status === 'IN_PROGRESS' ? 'Em Execução' :
                     m.status === 'COMPLETED' ? 'Concluída' : 'Cancelada'}
                  </span>
                </div>

                <h3 className="text-base font-bold text-white mb-2 leading-snug">{m.title}</h3>

                {m.location_name && (
                  <p className="text-xs text-violet-300 font-medium mb-2 flex items-center gap-1.5">
                    <MapPin className="w-3.5 h-3.5 text-violet-400" />
                    {m.location_name}
                  </p>
                )}

                <p className="text-xs text-gray-400 mb-4">
                  {m.city}/{m.state}
                </p>

                {/* Checklist Preview */}
                {m.checklist && m.checklist.length > 0 && (
                  <div className="bg-gray-800/40 border border-gray-800 rounded-xl p-3 mb-4 space-y-2">
                    <span className="text-xs font-semibold text-gray-400 flex items-center gap-1">
                      <ListChecks className="w-3.5 h-3.5 text-violet-400" /> Checklist de Campo
                    </span>
                    {m.checklist.map((c, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs text-gray-300">
                        <span className={`w-1.5 h-1.5 rounded-full ${c.done ? 'bg-green-400' : 'bg-gray-600'}`} />
                        <span className={c.done ? 'line-through text-gray-500' : ''}>{c.item}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="pt-4 border-t border-gray-800 flex items-center justify-between">
                <div>
                  <span className="text-xs text-gray-500 block">Remuneração</span>
                  <span className="text-base font-bold text-green-400 flex items-center">
                    R$ {m.reward_amount.toFixed(2)}
                  </span>
                </div>

                {canManage && (m.status === 'OPEN' || m.status === 'ASSIGNED' || m.status === 'IN_PROGRESS') && (
                  <Button
                    size="sm"
                    variant="secondary"
                    loading={statusMutation.isPending}
                    onClick={() => statusMutation.mutate({ id: m.id, status: 'CANCELLED' })}
                  >
                    Cancelar Missão
                  </Button>
                )}
                {m.status === 'COMPLETED' && (
                  <span className="text-xs font-bold text-green-400 flex items-center gap-1">
                    <CheckCircle2 className="w-4 h-4" /> Validada
                  </span>
                )}
                {m.status === 'CANCELLED' && (
                  <span className="text-xs font-bold text-red-400 flex items-center gap-1">
                    <ShieldAlert className="w-4 h-4" /> Cancelada
                  </span>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Modal Despachar Missão */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
          <div className="bg-gray-900 border border-gray-800 rounded-2xl w-full max-w-lg p-6 relative">
            <h2 className="text-xl font-bold text-white mb-4">Despachar Missão Territorial</h2>
            <form onSubmit={handleCreate} className="space-y-4">
              <Input
                label="Título da Missão"
                placeholder="Ex: Vistoria Técnica e Validação de Carteiras"
                value={title}
                onChange={e => setTitle(e.target.value)}
                required
              />
              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-1.5">
                  <label className="text-sm font-medium text-gray-300">Tipo de Missão</label>
                  <select
                    className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-violet-500 text-sm"
                    value={missionType}
                    onChange={e => setMissionType(e.target.value)}
                  >
                    <option value="VISTORIA">Vistoria</option>
                    <option value="CAPTACAO">Captação de Prédio</option>
                    <option value="CONFIRMACAO">Reconfirmação</option>
                    <option value="RECERTIFICACAO">Recertificação</option>
                    <option value="APOIO_OPERACIONAL">Apoio Operacional</option>
                  </select>
                </div>
                <Input
                  label="Remuneração (R$)"
                  type="number"
                  value={rewardAmount}
                  onChange={e => setRewardAmount(Number(e.target.value))}
                  required
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium text-gray-300">Vincular Prédio / Local (Opcional)</label>
                <select
                  className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-violet-500 text-sm"
                  value={locationId}
                  onChange={e => {
                    setLocationId(e.target.value)
                    const sel = locations?.find(l => l.id === e.target.value)
                    if (sel) {
                      setCity(sel.city)
                      setState(sel.state)
                    }
                  }}
                >
                  <option value="">Nenhum (Missão de Captação Geral)</option>
                  {locations?.map(l => (
                    <option key={l.id} value={l.id}>{l.name} ({l.city}/{l.state})</option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <Input
                  label="Cidade"
                  placeholder="Ex: Brasília"
                  value={city}
                  onChange={e => setCity(e.target.value)}
                  required
                />
                <Input
                  label="UF"
                  placeholder="DF"
                  maxLength={2}
                  value={state}
                  onChange={e => setState(e.target.value.toUpperCase())}
                  required
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-800">
                <Button type="button" variant="secondary" onClick={() => setIsModalOpen(false)}>
                  Cancelar
                </Button>
                <Button type="submit" loading={createMutation.isPending}>
                  Publicar Missão na Rede
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
