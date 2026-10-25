import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { GraduationCap, ArrowRight, BookOpen, Clock, ShieldCheck } from 'lucide-react'
import api from '../api/client'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import type { Course } from '../types'

export function StudentAcademyPage() {
  const navigate = useNavigate()

  const { data: courses, isLoading } = useQuery({
    queryKey: ['student-courses'],
    queryFn: () => api.get<Course[]>('/academy/courses?published_only=true').then(r => r.data),
  })

  return (
    <div>
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 bg-violet-600/20 text-violet-400 border border-violet-600/30 rounded-xl flex items-center justify-center">
            <GraduationCap className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Academy OPERAN</h1>
            <p className="text-gray-400 text-sm">Trilhas de formação operacional, protocolos de bancas e certificações oficiais</p>
          </div>
        </div>
      </div>

      <div className="bg-gradient-to-r from-violet-950/40 via-purple-900/20 to-gray-900 border border-violet-900/30 rounded-2xl p-6 mb-8 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-violet-400 bg-violet-500/10 border border-violet-500/20 px-3 py-1 rounded-full inline-block mb-2">
            Passaporte Operacional
          </span>
          <h2 className="text-lg font-bold text-white">Qualifique-se para ser convocado para missões e operações</h2>
          <p className="text-gray-400 text-sm max-w-2xl mt-1">
            Cada curso concluído emite uma certificação verificável no seu Passaporte Operacional, elevando seu score de reputação e habilitando você para funções de campo com maior remuneração.
          </p>
        </div>
        <Button variant="secondary" onClick={() => navigate('/admin/passport')}>
          <ShieldCheck className="w-4 h-4 mr-2 text-violet-400" /> Ver Meu Passaporte
        </Button>
      </div>

      <h2 className="text-lg font-bold text-white mb-4">Trilhas de Formação Disponíveis</h2>

      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <div className="animate-spin w-8 h-8 border-2 border-violet-600 border-t-transparent rounded-full" />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {courses?.map(course => {
            const version = course.versions?.[0]
            const firstLesson = version?.modules?.[0]?.lessons?.[0]
            const totalMinutes = version?.modules?.reduce((acc, m) => acc + (m.lessons?.reduce((a, l) => a + l.duration_minutes, 0) || 0), 0) || 0

            return (
              <Card key={course.id} className="flex flex-col justify-between overflow-hidden border border-gray-800 hover:border-violet-600/50 transition-all group">
                <div>
                  {course.thumbnail_url && (
                    <div className="h-44 -mx-6 -mt-6 mb-4 overflow-hidden relative">
                      <img
                        src={course.thumbnail_url}
                        alt={course.title}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      />
                      <div className="absolute inset-0 bg-gradient-to-t from-gray-950 via-gray-950/20 to-transparent" />
                      <span className="absolute bottom-3 left-3 text-xs font-semibold px-2.5 py-1 rounded-full bg-black/60 backdrop-blur-md text-gray-300 border border-white/10 flex items-center gap-1.5">
                        <Clock className="w-3 h-3 text-violet-400" />
                        {totalMinutes} min de carga
                      </span>
                    </div>
                  )}

                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-mono font-bold bg-violet-600/20 text-violet-400 border border-violet-600/30 px-2 py-0.5 rounded">
                      {version?.version_tag || 'v1.0'}
                    </span>
                    <span className="text-xs text-gray-400 font-medium">
                      {course.organization_id ? 'Banca Específica' : 'Formação Geral'}
                    </span>
                  </div>

                  <h3 className="text-lg font-bold text-white mb-2 leading-snug">{course.title}</h3>
                  <p className="text-gray-400 text-sm mb-6 line-clamp-3 leading-relaxed">{course.description}</p>
                </div>

                <div className="pt-4 border-t border-gray-800">
                  <Button
                    className="w-full justify-between"
                    onClick={() => {
                      if (firstLesson) {
                        navigate(`/admin/academy/course/${course.id}/lesson/${firstLesson.id}`)
                      }
                    }}
                  >
                    <span>Iniciar Formação</span>
                    <ArrowRight className="w-4 h-4 ml-2" />
                  </Button>
                </div>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
