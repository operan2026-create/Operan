import { useState } from 'react'
import { GraduationCap, Award, Settings, BookOpen, Copy, Check, ExternalLink, Sparkles, Plus, Share2 } from 'lucide-react'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { StudentAcademyPage } from './StudentAcademyPage'
import { OperationalPassportPage } from './OperationalPassportPage'
import { AcademyAdminPage } from './AcademyAdminPage'

export function AcademyHubPage() {
  const [activeTab, setActiveTab] = useState<'learn' | 'passport' | 'manage'>('learn')
  const [copied, setCopied] = useState(false)

  const inviteLink = '/admin/invitations'

  const handleCopyLink = () => {
    window.location.href = inviteLink
  }

  return (
    <div className="space-y-6">
      {/* Header Central Unificado da Academy */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-gray-800">
        <div>
          <h1 className="text-2xl font-black text-white flex items-center gap-3">
            <div className="w-9 h-9 bg-violet-600 rounded-xl flex items-center justify-center text-white">
              <GraduationCap className="w-5 h-5" />
            </div>
            Academy & Qualificação
          </h1>
          <p className="text-gray-400 text-sm mt-0.5">
            Trilhas de formação, Passaporte Operacional e emissão de habilitações para a rede
          </p>
        </div>

        {/* Box do Link de Convite para Colaboradores */}
        <div className="flex items-center gap-2 bg-gray-900 border border-violet-600/30 rounded-xl px-3 py-2">
          <Share2 className="w-4 h-4 text-violet-400 shrink-0" />
          <div className="text-xs">
            <span className="text-gray-400 block font-medium">Entrada por convite</span>
            <span className="text-gray-500 font-mono truncate max-w-[220px] block">
              /admin/invitations
            </span>
          </div>
          <Button size="sm" variant={copied ? 'secondary' : 'primary'} onClick={handleCopyLink} className="ml-2">
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 mr-1 text-green-400" />
                Abrindo...
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5 mr-1" />
                Gerenciar convites
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Seletor de Abas Internas da Academy */}
      <div className="flex items-center gap-2 border-b border-gray-800 pb-2">
        <button
          onClick={() => setActiveTab('learn')}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl font-semibold text-sm transition-all ${
            activeTab === 'learn'
              ? 'bg-violet-600 text-white shadow-lg shadow-violet-600/20'
              : 'text-gray-400 hover:text-white hover:bg-gray-900'
          }`}
        >
          <BookOpen className="w-4 h-4" />
          Trilhas & Aulas
        </button>

        <button
          onClick={() => setActiveTab('passport')}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl font-semibold text-sm transition-all ${
            activeTab === 'passport'
              ? 'bg-violet-600 text-white shadow-lg shadow-violet-600/20'
              : 'text-gray-400 hover:text-white hover:bg-gray-900'
          }`}
        >
          <Award className="w-4 h-4" />
          Meu Passaporte Operacional
        </button>

        <button
          onClick={() => setActiveTab('manage')}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl font-semibold text-sm transition-all ${
            activeTab === 'manage'
              ? 'bg-violet-600 text-white shadow-lg shadow-violet-600/20'
              : 'text-gray-400 hover:text-white hover:bg-gray-900'
          }`}
        >
          <Settings className="w-4 h-4" />
          Gestão de Conteúdos
        </button>
      </div>

      {/* Conteúdo da Aba Selecionada */}
      <div className="pt-2">
        {activeTab === 'learn' && <StudentAcademyPage />}
        {activeTab === 'passport' && <OperationalPassportPage />}
        {activeTab === 'manage' && <AcademyAdminPage />}
      </div>
    </div>
  )
}
