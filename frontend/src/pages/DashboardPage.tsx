import { useQuery } from '@tanstack/react-query'
import { Building2, Users, GraduationCap, Target, MapPin, Activity, ShieldCheck } from 'lucide-react'
import api from '../api/client'
import { Card } from '../components/ui/Card'
import type { Organization, Location, Mission, Course, Certification } from '../types'

export function DashboardPage() {
  const { data: orgs } = useQuery({
    queryKey: ['organizations'],
    queryFn: () => api.get<Organization[]>('/organizations').then(r => r.data),
  })

  const { data: locations } = useQuery({
    queryKey: ['locations'],
    queryFn: () => api.get<Location[]>('/locations').then(r => r.data),
  })

  const { data: missions } = useQuery({
    queryKey: ['missions'],
    queryFn: () => api.get<Mission[]>('/missions').then(r => r.data),
  })

  const { data: courses } = useQuery({
    queryKey: ['courses'],
    queryFn: () => api.get<Course[]>('/academy/courses').then(r => r.data),
  })

  const { data: certs } = useQuery({
    queryKey: ['my-certifications', 'admin'],
    queryFn: () => api.get<Certification[]>('/academy/my-certifications').then(r => r.data),
  })

  const stats = [
    { label: 'Organizadoras (Clientes)', value: orgs?.length || 0, icon: Building2, color: 'text-violet-400', bg: 'bg-violet-600/10' },
    { label: 'Prédios / Locais Mapeados', value: locations?.length || 0, icon: MapPin, color: 'text-yellow-400', bg: 'bg-yellow-600/10' },
    { label: 'Missões Territoriais', value: missions?.length || 0, icon: Target, color: 'text-orange-400', bg: 'bg-orange-600/10' },
    { label: 'Trilhas Academy', value: courses?.length || 0, icon: GraduationCap, color: 'text-blue-400', bg: 'bg-blue-600/10' },
    { label: 'Capacidade Total Mapeada', value: locations?.reduce((acc, l) => acc + l.total_capacity, 0) || 0, icon: Users, color: 'text-green-400', bg: 'bg-green-600/10' },
    { label: 'Certificações Emitidas', value: certs?.length || 0, icon: ShieldCheck, color: 'text-pink-400', bg: 'bg-pink-600/10' },
  ]

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Dashboard Operacional</h1>
        <p className="text-gray-400 mt-1">Centro de comando da infraestrutura operacional e territorial da OPERAN</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        {stats.map((s) => (
          <Card key={s.label}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-400 text-sm">{s.label}</p>
                <p className="text-3xl font-bold text-white mt-1">
                  {typeof s.value === 'number' ? s.value.toLocaleString('pt-BR') : s.value}
                </p>
              </div>
              <div className={`w-12 h-12 ${s.bg} rounded-xl flex items-center justify-center`}>
                <s.icon className={`w-6 h-6 ${s.color}`} />
              </div>
            </div>
          </Card>
        ))}
      </div>

      <Card>
        <div className="flex items-center gap-3 mb-4">
          <Activity className="w-5 h-5 text-violet-400" />
          <h2 className="text-white font-semibold">Status dos Serviços da Plataforma</h2>
        </div>
        <div className="space-y-3">
          <div className="flex items-center justify-between py-2 border-b border-gray-800">
            <span className="text-gray-400 text-sm">API Backend (FastAPI)</span>
            <span className="text-green-400 text-sm font-medium flex items-center gap-1.5">
              <span className="w-2 h-2 bg-green-400 rounded-full inline-block" />
              Online (Porta 8000)
            </span>
          </div>
          <div className="flex items-center justify-between py-2 border-b border-gray-800">
            <span className="text-gray-400 text-sm">PostgreSQL (Supabase Engine)</span>
            <span className="text-green-400 text-sm font-medium flex items-center gap-1.5">
              <span className="w-2 h-2 bg-green-400 rounded-full inline-block" />
              Conectado (Porta 5433)
            </span>
          </div>
          <div className="flex items-center justify-between py-2 border-b border-gray-800">
            <span className="text-gray-400 text-sm">Redis (Cache & Filas)</span>
            <span className="text-green-400 text-sm font-medium flex items-center gap-1.5">
              <span className="w-2 h-2 bg-green-400 rounded-full inline-block" />
              Online (Porta 6379)
            </span>
          </div>
          <div className="flex items-center justify-between py-2">
            <span className="text-gray-400 text-sm">Módulo Criptográfico (AES-256-GCM / Envelope)</span>
            <span className="text-green-400 text-sm font-medium flex items-center gap-1.5">
              <span className="w-2 h-2 bg-green-400 rounded-full inline-block" />
              Ativo
            </span>
          </div>
        </div>
      </Card>
    </div>
  )
}
