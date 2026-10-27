import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { MapPin, Plus, Search, Building, Users, CheckCircle2, AlertTriangle, ShieldCheck, Wind, Accessibility } from 'lucide-react'
import api from '../api/client'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { useArea } from '../hooks/useArea'
import { useAuth } from '../hooks/useAuth'
import { LocationWorkflowModal } from '../components/LocationWorkflowModal'
import type { Location } from '../types'

const statusConfig = {
  DECLARADO: {
    label: 'Declarado',
    color: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    icon: AlertTriangle,
    dot: 'bg-yellow-400',
  },
  VISTORIADO: {
    label: 'Vistoriado',
    color: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    icon: ShieldCheck,
    dot: 'bg-blue-400',
  },
  CONFIRMADO: {
    label: 'Confirmado',
    color: 'bg-green-500/20 text-green-400 border-green-500/30',
    icon: CheckCircle2,
    dot: 'bg-green-400',
  },
}

export function LocationsPage() {
  const queryClient = useQueryClient()
  const area = useArea()
  const { user } = useAuth()
  const isAdmin = area === 'admin'
  const canCreate = isAdmin || user?.roles?.includes('CLIENT_ADMIN')
  const canDecide = isAdmin || user?.roles?.includes('CLIENT_ADMIN')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('ALL')
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [workflowLocation, setWorkflowLocation] = useState<Location | null>(null)

  // Form State
  const [name, setName] = useState('')
  const [address, setAddress] = useState('')
  const [city, setCity] = useState('')
  const [state, setState] = useState('DF')
  const [totalRooms, setTotalRooms] = useState(20)
  const [totalCapacity, setTotalCapacity] = useState(600)
  const [hasAccessibility, setHasAccessibility] = useState(true)
  const [hasAirConditioning, setHasAirConditioning] = useState(true)

  const { data: locations, isLoading } = useQuery({
    queryKey: ['locations', area],
    queryFn: () => api.get<Location[]>('/locations').then(r => r.data),
  })

  const createMutation = useMutation({
    mutationFn: (newLoc: any) => api.post('/locations', newLoc),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['locations', area] })
      setIsModalOpen(false)
      setName('')
      setAddress('')
      setCity('')
    },
  })

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.patch(`/locations/${id}/status`, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['locations', area] })
    },
  })

  const filtered = locations?.filter(l => {
    const matchesSearch = l.name.toLowerCase().includes(search.toLowerCase()) ||
                          l.city.toLowerCase().includes(search.toLowerCase())
    const matchesStatus = statusFilter === 'ALL' || l.status === statusFilter
    return matchesSearch && matchesStatus
  }) || []

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate({
      name,
      address,
      city,
      state,
      total_rooms: Number(totalRooms),
      total_capacity: Number(totalCapacity),
      has_accessibility: hasAccessibility,
      has_air_conditioning: hasAirConditioning,
      status: 'DECLARADO',
    })
  }

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Building className="w-7 h-7 text-violet-400" />
            Locais de Aplicação (Prédios & Escolas)
          </h1>
          <p className="text-gray-400 mt-1">
            Rede territorial mapeada, capacidade de salas, infraestrutura física e validação em 3 níveis
          </p>
        </div>
        {canCreate && (
          <Button onClick={() => setIsModalOpen(true)}>
            <Plus className="w-4 h-4 mr-2" /> Cadastrar Prédio / Local
          </Button>
        )}
      </div>

      {/* Filtros */}
      <Card className="mb-6">
        <div className="flex flex-col md:flex-row items-center gap-4">
          <div className="relative flex-1 w-full">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input
              className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-10 pr-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500 text-sm"
              placeholder="Buscar por nome do local ou cidade..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>

          <div className="flex items-center gap-2 w-full md:w-auto overflow-x-auto pb-1 md:pb-0">
            {['ALL', 'DECLARADO', 'VISTORIADO', 'CONFIRMADO'].map(st => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors ${
                  statusFilter === st
                    ? 'bg-violet-600 text-white'
                    : 'bg-gray-800 text-gray-400 hover:text-white'
                }`}
              >
                {st === 'ALL' ? 'Todos os Prédios' : st}
              </button>
            ))}
          </div>
        </div>
      </Card>

      {/* Grid de Prédios */}
      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <div className="animate-spin w-8 h-8 border-2 border-violet-600 border-t-transparent rounded-full" />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filtered.map(loc => {
            const conf = statusConfig[loc.status]
            return (
              <Card key={loc.id} className="flex flex-col justify-between border border-gray-800 hover:border-violet-600/40 transition-all group">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className={`text-xs font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full border flex items-center gap-1.5 ${conf.color}`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${conf.dot}`} />
                      {conf.label}
                    </span>
                    <span className="text-xs text-gray-500 font-mono">
                      Score: <strong className="text-violet-400">{loc.reliability_score}%</strong>
                    </span>
                  </div>

                  <h3 className="text-lg font-bold text-white mb-1 leading-snug group-hover:text-violet-300 transition-colors">
                    {loc.name}
                  </h3>
                  <p className="text-gray-400 text-xs flex items-center gap-1 mb-4">
                    <MapPin className="w-3.5 h-3.5 text-gray-500 shrink-0" />
                    {loc.address} • {loc.city}/{loc.state}
                  </p>

                  <div className="grid grid-cols-2 gap-2 bg-gray-800/40 border border-gray-800 rounded-xl p-3 mb-4 text-xs">
                    <div>
                      <span className="text-gray-500 block">Capacidade Total</span>
                      <span className="text-white font-bold text-sm flex items-center gap-1 mt-0.5">
                        <Users className="w-3.5 h-3.5 text-violet-400" />
                        {loc.total_capacity} carteiras
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-500 block">Salas de Prova</span>
                      <span className="text-white font-bold text-sm mt-0.5 block">
                        {loc.total_rooms} salas
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 text-xs text-gray-400">
                    <span className={`flex items-center gap-1 ${loc.has_accessibility ? 'text-green-400' : 'text-gray-600'}`}>
                      <Accessibility className="w-3.5 h-3.5" />
                      {loc.has_accessibility ? 'Acessível' : 'Sem rampa'}
                    </span>
                    <span className={`flex items-center gap-1 ${loc.has_air_conditioning ? 'text-green-400' : 'text-gray-600'}`}>
                      <Wind className="w-3.5 h-3.5" />
                      {loc.has_air_conditioning ? 'Ar Climatizado' : 'Ventilador'}
                    </span>
                  </div>
                </div>

                {/* Transição de Estado da Validação */}
                <div className="pt-4 border-t border-gray-800 mt-5 flex items-center justify-between gap-2">
                  {canDecide && loc.status === 'DECLARADO' && (
                    <Button
                      size="sm"
                      variant="secondary"
                      className="w-full text-blue-400 hover:text-blue-300 border border-blue-500/30"
                      onClick={() => statusMutation.mutate({ id: loc.id, status: 'VISTORIADO' })}
                    >
                      Aprovar Vistoria (Vistoriado)
                    </Button>
                  )}
                  {canDecide && loc.status === 'VISTORIADO' && (
                    <Button
                      size="sm"
                      className="w-full bg-green-600 hover:bg-green-700 text-white"
                      onClick={() => statusMutation.mutate({ id: loc.id, status: 'CONFIRMADO' })}
                    >
                      Confirmar p/ Operação (Confirmado)
                    </Button>
                  )}
                  {loc.status === 'CONFIRMADO' && (
                    <span className="text-xs text-green-400 font-semibold flex items-center gap-1.5 w-full justify-center py-1">
                      <CheckCircle2 className="w-4 h-4" />
                      Pronto para Operação
                    </span>
                  )}
                  {!canDecide && loc.status !== 'CONFIRMADO' && (
                    <span className="text-xs text-yellow-400 font-semibold flex items-center gap-1.5 w-full justify-center py-1">
                      <AlertTriangle className="w-4 h-4" />
                      Em validação pela OPERAN
                    </span>
                  )}
                </div>
              </Card>
            )
          })}
        </div>
      )}

      {workflowLocation && (
        <LocationWorkflowModal
          location={workflowLocation}
          onClose={() => setWorkflowLocation(null)}
        />
      )}

      {/* Modal Novo Local */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
          <div className="bg-gray-900 border border-gray-800 rounded-2xl w-full max-w-lg p-6 relative">
            <h2 className="text-xl font-bold text-white mb-4">Cadastrar Local de Aplicação</h2>
            <form onSubmit={handleCreate} className="space-y-4">
              <Input
                label="Nome do Prédio / Escola / Campus"
                placeholder="Ex: Centro Universitário de Brasília - UniCEUB"
                value={name}
                onChange={e => setName(e.target.value)}
                required
              />
              <Input
                label="Endereço Completo"
                placeholder="Ex: SEPN 707/907 Campus Universitário"
                value={address}
                onChange={e => setAddress(e.target.value)}
                required
              />
              <div className="grid grid-cols-2 gap-4">
                <Input
                  label="Cidade"
                  placeholder="Ex: Brasília"
                  value={city}
                  onChange={e => setCity(e.target.value)}
                  required
                />
                <Input
                  label="Estado (UF)"
                  placeholder="DF"
                  maxLength={2}
                  value={state}
                  onChange={e => setState(e.target.value.toUpperCase())}
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <Input
                  label="Total de Salas"
                  type="number"
                  value={totalRooms}
                  onChange={e => setTotalRooms(Number(e.target.value))}
                  required
                />
                <Input
                  label="Capacidade Total (Carteiras)"
                  type="number"
                  value={totalCapacity}
                  onChange={e => setTotalCapacity(Number(e.target.value))}
                  required
                />
              </div>

              <div className="flex items-center gap-6 pt-2">
                <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={hasAccessibility}
                    onChange={e => setHasAccessibility(e.target.checked)}
                    className="rounded bg-gray-800 border-gray-700 text-violet-600 focus:ring-violet-500"
                  />
                  Possui Acessibilidade
                </label>
                <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={hasAirConditioning}
                    onChange={e => setHasAirConditioning(e.target.checked)}
                    className="rounded bg-gray-800 border-gray-700 text-violet-600 focus:ring-violet-500"
                  />
                  Ar-condicionado
                </label>
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-800">
                <Button type="button" variant="secondary" onClick={() => setIsModalOpen(false)}>
                  Cancelar
                </Button>
                <Button type="submit" loading={createMutation.isPending}>
                  Cadastrar Prédio
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
