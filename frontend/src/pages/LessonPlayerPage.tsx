import { useState } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, CheckCircle2, ChevronRight, PlayCircle, FileText, Award, Sparkles } from 'lucide-react'
import api from '../api/client'
import { Button } from '../components/ui/Button'
import { getApiErrorMessage } from '../lib/errors'
import type { Course } from '../types'

export function LessonPlayerPage() {
  const { courseId, lessonId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const [certifiedSuccess, setCertifiedSuccess] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')

  const academyBase = location.pathname.startsWith('/admin') ? '/admin/academy' : '/participante/academy'
  const lessonPath = (id: string) => `${academyBase}/course/${courseId}/lesson/${id}`

  const { data: course, isLoading } = useQuery({
    queryKey: ['course-detail', courseId],
    queryFn: () => api.get<Course>(`/academy/courses/${courseId}`).then(r => r.data),
  })

  const version = course?.versions?.[0]
  const allLessons = version?.modules?.flatMap(m => m.lessons) || []
  const currentLesson = allLessons.find(l => l.id === lessonId) || allLessons[0]
  const currentIndex = allLessons.findIndex(l => l.id === currentLesson?.id)
  const isLastLesson = currentIndex === allLessons.length - 1

  const completeMutation = useMutation({
    mutationFn: (id: string) => api.post(`/academy/lessons/${id}/complete`),
  })

  const certifyMutation = useMutation({
    mutationFn: () => api.post(`/academy/versions/${version?.id}/certify`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['my-certifications', 'participante'] })
      queryClient.invalidateQueries({ queryKey: ['my-certifications', 'admin'] })
      setCertifiedSuccess(true)
    },
    onError: (err: any) => {
      setErrorMessage(getApiErrorMessage(err, 'Não foi possível emitir o certificado.'))
    },
  })

  const handleAdvance = async () => {
    if (!currentLesson) return
    setErrorMessage('')
    try {
      await completeMutation.mutateAsync(currentLesson.id)
      if (isLastLesson) {
        certifyMutation.mutate()
      } else {
        navigate(lessonPath(allLessons[currentIndex + 1].id))
      }
    } catch (err: any) {
      setErrorMessage(getApiErrorMessage(err, 'Não foi possível registrar a conclusão da aula.'))
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-2 border-violet-600 border-t-transparent rounded-full" />
      </div>
    )
  }

  if (certifiedSuccess) {
    return (
      <div className="max-w-2xl mx-auto py-12 text-center">
        <div className="w-20 h-20 bg-green-500/20 text-green-400 border border-green-500/30 rounded-3xl flex items-center justify-center mx-auto mb-6">
          <Award className="w-10 h-10" />
        </div>
        <span className="text-xs font-bold uppercase tracking-widest text-violet-400 bg-violet-600/20 px-3 py-1 rounded-full">
          Passaporte Operacional Atualizado
        </span>
        <h1 className="text-3xl font-extrabold text-white mt-4 mb-2">Parabéns! Formação Concluída</h1>
        <p className="text-gray-400 text-base max-w-lg mx-auto mb-8">
          Você completou com sucesso a trilha <strong className="text-white">{course?.title}</strong> ({version?.version_tag}). Seu certificado já foi emitido e registrado no seu Passaporte Operacional.
        </p>
        <div className="flex items-center justify-center gap-4">
          <Button size="lg" onClick={() => navigate(academyBase)}>
            <Sparkles className="w-5 h-5 mr-2" /> Voltar para Trilhas
          </Button>
          <Button variant="secondary" size="lg" onClick={() => navigate(academyBase)}>
            Voltar para Trilhas
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div>
      {/* Header com Navegação */}
      <div className="flex items-center justify-between mb-6 pb-4 border-b border-gray-800">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate(academyBase)}
            className="p-2 hover:bg-gray-800 text-gray-400 hover:text-white rounded-lg transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <span className="text-xs font-semibold text-violet-400 uppercase tracking-wider">{course?.title}</span>
            <h1 className="text-xl font-bold text-white">{currentLesson?.title}</h1>
          </div>
        </div>
        <span className="text-xs text-gray-500 font-mono">
          Aula {currentIndex + 1} de {allLessons.length}
        </span>
      </div>

      {/* Grid Principal: Player e Sidebar de Aulas */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Conteúdo da Aula (2 colunas) */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8 min-h-[420px] flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-2 text-xs font-semibold text-gray-400 mb-4">
                <FileText className="w-4 h-4 text-violet-400" />
                <span>Protocolo & Conteúdo Teórico</span>
                <span>•</span>
                <span>{currentLesson?.duration_minutes} min de leitura estimada</span>
              </div>
              <div className="prose prose-invert max-w-none text-gray-300 text-base leading-relaxed space-y-4">
                <p className="text-lg font-medium text-white mb-4">
                  {currentLesson?.title}
                </p>
                <div className="bg-gray-800/60 border border-gray-700/50 rounded-xl p-5 text-gray-300 whitespace-pre-line leading-relaxed">
                  {currentLesson?.content || 'Conteúdo em processamento pela coordenação acadêmica.'}
                </div>
              </div>
            </div>

            {/* Ações de Navegação de Aula */}
            {errorMessage && (
              <p className="mt-4 text-sm text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-3 py-2">
                {errorMessage}
              </p>
            )}

            <div className="pt-6 border-t border-gray-800 flex items-center justify-between mt-8">
              {currentIndex > 0 ? (
                <Button
                  variant="secondary"
                  onClick={() => navigate(lessonPath(allLessons[currentIndex - 1].id))}
                >
                  Aula Anterior
                </Button>
              ) : <div />}

              {isLastLesson ? (
                <Button
                  onClick={handleAdvance}
                  loading={completeMutation.isPending || certifyMutation.isPending}
                  className="bg-green-600 hover:bg-green-700"
                >
                  <Award className="w-4 h-4 mr-2" />
                  Concluir e Emitir Certificado
                </Button>
              ) : (
                <Button
                  onClick={handleAdvance}
                  loading={completeMutation.isPending}
                >
                  Próxima Aula
                  <ChevronRight className="w-4 h-4 ml-2" />
                </Button>
              )}
            </div>
          </div>
        </div>

        {/* Sidebar de Módulos & Aulas (1 coluna) */}
        <div className="space-y-4">
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
            <h2 className="text-sm font-bold uppercase tracking-wider text-gray-400 mb-4">
              Conteúdo da Formação
            </h2>
            <div className="space-y-4">
              {version?.modules?.map(m => (
                <div key={m.id} className="space-y-2">
                  <p className="text-xs font-semibold text-violet-400 px-2">{m.title}</p>
                  <div className="space-y-1">
                    {m.lessons?.map((les, idx) => {
                      const isCurrent = les.id === currentLesson?.id
                      return (
                        <button
                          key={les.id}
                          onClick={() => navigate(lessonPath(les.id))}
                          className={`w-full text-left px-3 py-2 rounded-xl text-sm font-medium flex items-center gap-3 transition-colors ${
                            isCurrent
                              ? 'bg-violet-600/20 text-violet-300 border border-violet-600/30'
                              : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                          }`}
                        >
                          {isCurrent ? (
                            <PlayCircle className="w-4 h-4 text-violet-400 shrink-0" />
                          ) : (
                            <CheckCircle2 className="w-4 h-4 text-gray-600 shrink-0" />
                          )}
                          <span className="truncate">{les.title}</span>
                        </button>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
