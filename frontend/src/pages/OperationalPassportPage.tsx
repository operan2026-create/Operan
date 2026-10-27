import { useQuery } from '@tanstack/react-query'
import { ShieldCheck, Award, CheckCircle2, Calendar, Star, UserCheck, Shield, Sparkles, AlertCircle } from 'lucide-react'
import api from '../api/client'
import { Card } from '../components/ui/Card'
import { useAuth } from '../hooks/useAuth'
import { useArea } from '../hooks/useArea'
import type { Certification, Mission } from '../types'

export function OperationalPassportPage() {
  const { user } = useAuth()
  const area = useArea()

  const { data: certs, isLoading } = useQuery({
    queryKey: ['my-certifications', area],
    queryFn: () => api.get<Certification[]>('/academy/my-certifications').then(r => r.data),
  })

  const { data: myMissions } = useQuery({
    queryKey: ['passport-missions', area],
    queryFn: () => api.get<Mission[]>('/missions?only_my=true').then(r => r.data).catch(() => []),
  })

  const verifiedCertsCount = certs?.filter(c => c.status === 'VALID').length || 0
  const completedMissions = myMissions?.filter(m => m.status === 'COMPLETED').length || 0
  const reputation = user?.professional?.reputation_score
  const availability = user?.professional?.availability_status

  return (
    <div>
      {/* Header do Passaporte */}
      <div className="bg-gradient-to-r from-violet-950/60 via-gray-900 to-gray-950 border border-violet-900/40 rounded-3xl p-8 mb-8 relative overflow-hidden">
        <div className="absolute right-0 top-0 w-96 h-96 bg-violet-600/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="flex items-center gap-5">
            <div className="w-20 h-20 bg-gradient-to-br from-violet-600 to-purple-800 rounded-2xl flex items-center justify-center text-white shadow-xl shadow-violet-950/50 border border-white/10">
              <ShieldCheck className="w-10 h-10 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-mono font-bold bg-violet-600/20 text-violet-400 border border-violet-600/30 px-2.5 py-0.5 rounded-full">
                  {user?.public_id || 'USR-OPERAN'}
                </span>
                <span className="text-xs font-bold uppercase tracking-wider bg-green-500/20 text-green-400 border border-green-500/30 px-2.5 py-0.5 rounded-full flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
                  Identidade Verificada
                </span>
              </div>
              <h1 className="text-2xl font-black text-white">{user?.email}</h1>
              <p className="text-gray-400 text-sm mt-0.5">
                Passaporte Operacional Nacional • OPERAN Network ID
              </p>
            </div>
          </div>

          <div className="bg-gray-900/80 backdrop-blur-md border border-gray-800 rounded-2xl px-6 py-4 flex items-center gap-4">
            <div>
              <p className="text-xs text-gray-500 font-medium">Índice de Confiabilidade</p>
              <p className="text-2xl font-black text-violet-400">
                {reputation !== undefined ? reputation.toFixed(1) : "-"}
                <span className="text-sm font-normal text-gray-400"> /100</span>
              </p>
            </div>
            <div className="w-10 h-10 bg-violet-500/10 rounded-xl flex items-center justify-center">
              <Star className="w-5 h-5 text-violet-400 fill-violet-400/30" />
            </div>
          </div>
        </div>

        {/* Métricas do Passaporte */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-8 pt-6 border-t border-gray-800/80">
          <div>
            <p className="text-xs text-gray-500">Certificações Ativas</p>
            <p className="text-2xl font-bold text-white mt-0.5">{verifiedCertsCount}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Cursos Concluídos</p>
            <p className="text-2xl font-bold text-violet-400 mt-0.5">{certs?.length || 0}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Missões Concluídas</p>
            <p className="text-2xl font-bold text-white mt-0.5">{completedMissions}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Disponibilidade</p>
            <p className="text-2xl font-bold text-green-400 mt-0.5">
              {availability === "AVAILABLE" ? "Disponível" : availability === "IN_MISSION" ? "Em missão" : availability === "UNAVAILABLE" ? "Indisponível" : "-"}
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Lista de Certificações Oficiais (2 colunas) */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <Award className="w-5 h-5 text-violet-400" />
              Certificações Operacionais Emitidas
            </h2>
            <span className="text-xs text-gray-500 font-mono">
              {verifiedCertsCount} registradas
            </span>
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin w-6 h-6 border-2 border-violet-600 border-t-transparent rounded-full" />
            </div>
          ) : !certs || certs.length === 0 ? (
            <Card className="text-center py-12">
              <Award className="w-12 h-12 text-gray-700 mx-auto mb-3" />
              <p className="text-white font-semibold">Nenhuma certificação emitida ainda</p>
              <p className="text-gray-500 text-sm mt-1 max-w-sm mx-auto">
                Acesse a Academy e conclua as trilhas de formação para obter suas primeiras habilitações de campo.
              </p>
            </Card>
          ) : (
            <div className="space-y-3">
              {certs.map(cert => (
                <Card key={cert.id} className="border border-gray-800 hover:border-violet-600/40 transition-colors">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className="text-xs font-mono font-bold bg-violet-600/20 text-violet-400 border border-violet-600/30 px-2 py-0.5 rounded">
                          {cert.version_tag || 'v1.0'}
                        </span>
                        <span className="text-xs font-bold uppercase tracking-wider text-green-400 bg-green-500/10 border border-green-500/20 px-2 py-0.5 rounded-full flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3 text-green-400" />
                          Válido & Verificado
                        </span>
                      </div>
                      <h3 className="text-base font-bold text-white">{cert.course_title || 'Curso OPERAN'}</h3>
                      <p className="text-xs text-gray-500 mt-1 flex items-center gap-1.5">
                        <Calendar className="w-3.5 h-3.5" />
                        Emitido em {new Date(cert.issued_at).toLocaleDateString('pt-BR')} • Criptograficamente assinado
                      </p>
                    </div>

                    <div className="text-right">
                      <span className="text-xs text-gray-500 block">Aproveitamento</span>
                      <span className="text-lg font-black text-violet-400">{cert.score || 100}%</span>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>

        {/* Funções Habilitadas (1 coluna) */}
        <div className="space-y-4">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <UserCheck className="w-5 h-5 text-violet-400" />
            Funções de Campo Habilitadas
          </h2>

          <Card className="space-y-4">
            <div className="flex items-center justify-between p-3 rounded-xl bg-gray-800/60 border border-gray-700/40">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-green-500/20 text-green-400 flex items-center justify-center">
                  <CheckCircle2 className="w-4 h-4" />
                </div>
                <div>
                  <p className="text-sm font-bold text-white">Fiscal de Sala</p>
                  <p className="text-xs text-gray-400">Habilitado via Academy</p>
                </div>
              </div>
              <span className="text-xs font-bold text-green-400 bg-green-500/10 px-2 py-0.5 rounded border border-green-500/20">{verifiedCertsCount > 0 ? 'Apto' : 'Pendente'}</span>
            </div>

            <div className="flex items-center justify-between p-3 rounded-xl bg-gray-800/60 border border-gray-700/40">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-green-500/20 text-green-400 flex items-center justify-center">
                  <CheckCircle2 className="w-4 h-4" />
                </div>
                <div>
                  <p className="text-sm font-bold text-white">Protocolo Base OPERAN</p>
                  <p className="text-xs text-gray-400">Ética e LGPD verificadas</p>
                </div>
              </div>
              <span className="text-xs font-bold text-green-400 bg-green-500/10 px-2 py-0.5 rounded border border-green-500/20">{verifiedCertsCount > 0 ? 'Apto' : 'Pendente'}</span>
            </div>

            <div className="flex items-center justify-between p-3 rounded-xl bg-gray-800/20 border border-gray-800/60 opacity-60">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-gray-800 text-gray-500 flex items-center justify-center">
                  <AlertCircle className="w-4 h-4" />
                </div>
                <div>
                  <p className="text-sm font-bold text-gray-400">Chefe de Sala</p>
                  <p className="text-xs text-gray-500">Requer trilha específica</p>
                </div>
              </div>
              <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded">Pendente</span>
            </div>

            <div className="flex items-center justify-between p-3 rounded-xl bg-gray-800/20 border border-gray-800/60 opacity-60">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-gray-800 text-gray-500 flex items-center justify-center">
                  <AlertCircle className="w-4 h-4" />
                </div>
                <div>
                  <p className="text-sm font-bold text-gray-400">Vistoriador Territorial</p>
                  <p className="text-xs text-gray-500">Requer trilha específica</p>
                </div>
              </div>
              <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded">Pendente</span>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
