import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { GraduationCap, Plus, BookOpen, Layers, CheckCircle2, Clock } from 'lucide-react'
import api from '../api/client'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import type { Course } from '../types'

export function AcademyAdminPage() {
  const queryClient = useQueryClient()
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [thumbnailUrl, setThumbnailUrl] = useState('')
  const [status, setStatus] = useState<'DRAFT' | 'PUBLISHED'>('PUBLISHED')

  const { data: courses, isLoading } = useQuery({
    queryKey: ['admin-courses'],
    queryFn: () => api.get<Course[]>('/academy/courses').then(r => r.data),
  })

  const createMutation = useMutation({
    mutationFn: (newCourse: any) => api.post('/academy/courses', newCourse),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-courses'] })
      setIsModalOpen(false)
      setTitle('')
      setDescription('')
      setThumbnailUrl('')
    },
  })

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate({
      title,
      description,
      thumbnail_url: thumbnailUrl || undefined,
      status,
    })
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Gestão da Academy</h1>
          <p className="text-gray-400 mt-1">Crie e versione trilhas de formação, módulos e protocolos operacionais</p>
        </div>
        <Button onClick={() => setIsModalOpen(true)}>
          <Plus className="w-4 h-4 mr-2" /> Novo Curso / Trilha
        </Button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <div className="animate-spin w-8 h-8 border-2 border-violet-600 border-t-transparent rounded-full" />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {courses?.map(course => {
            const activeVersion = course.versions?.[0]
            const modulesCount = activeVersion?.modules?.length || 0
            const lessonsCount = activeVersion?.modules?.reduce((acc, m) => acc + (m.lessons?.length || 0), 0) || 0

            return (
              <Card key={course.id} className="flex flex-col justify-between overflow-hidden border border-gray-800 hover:border-violet-600/50 transition-all group">
                <div>
                  {course.thumbnail_url ? (
                    <div className="h-40 -mx-6 -mt-6 mb-4 overflow-hidden relative">
                      <img
                        src={course.thumbnail_url}
                        alt={course.title}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      />
                      <div className="absolute inset-0 bg-gradient-to-t from-gray-950 via-transparent to-transparent" />
                      <span className={`absolute top-3 right-3 text-xs font-semibold px-2.5 py-1 rounded-full border ${
                        course.status === 'PUBLISHED'
                          ? 'bg-green-500/20 text-green-400 border-green-500/30'
                          : 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
                      }`}>
                        {course.status === 'PUBLISHED' ? 'Publicado' : 'Rascunho'}
                      </span>
                    </div>
                  ) : null}

                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-mono font-bold bg-violet-600/20 text-violet-400 border border-violet-600/30 px-2 py-0.5 rounded">
                      {activeVersion?.version_tag || 'v1.0'}
                    </span>
                    <span className="text-xs text-gray-500">
                      {course.organization_id ? 'Organizadora' : 'Global OPERAN'}
                    </span>
                  </div>

                  <h3 className="text-lg font-bold text-white mb-2 line-clamp-1">{course.title}</h3>
                  <p className="text-gray-400 text-sm mb-4 line-clamp-3 leading-relaxed">{course.description || 'Sem descrição cadastrada.'}</p>
                </div>

                <div className="pt-4 border-t border-gray-800 flex items-center justify-between text-xs text-gray-400">
                  <span className="flex items-center gap-1.5">
                    <Layers className="w-3.5 h-3.5 text-violet-400" />
                    {modulesCount} {modulesCount === 1 ? 'módulo' : 'módulos'}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <BookOpen className="w-3.5 h-3.5 text-blue-400" />
                    {lessonsCount} {lessonsCount === 1 ? 'aula' : 'aulas'}
                  </span>
                </div>
              </Card>
            )
          })}
        </div>
      )}

      {/* Modal Criar Curso */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
          <div className="bg-gray-900 border border-gray-800 rounded-2xl w-full max-w-lg p-6 relative">
            <h2 className="text-xl font-bold text-white mb-4">Novo Curso / Trilha de Formação</h2>
            <form onSubmit={handleCreate} className="space-y-4">
              <Input
                label="Título do Curso"
                placeholder="Ex: Formação para Chefe de Sala"
                value={title}
                onChange={e => setTitle(e.target.value)}
                required
              />
              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium text-gray-300">Descrição / Ementa</label>
                <textarea
                  className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500"
                  rows={3}
                  placeholder="Objetivos do treinamento, protocolos abordados e público-alvo..."
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                />
              </div>
              <Input
                label="URL da Imagem de Capa (Thumbnail)"
                placeholder="https://exemplo.com/imagem.jpg"
                value={thumbnailUrl}
                onChange={e => setThumbnailUrl(e.target.value)}
              />
              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium text-gray-300">Status</label>
                <select
                  className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
                  value={status}
                  onChange={e => setStatus(e.target.value as any)}
                >
                  <option value="PUBLISHED">Publicado (Disponível na Rede)</option>
                  <option value="DRAFT">Rascunho (Interno)</option>
                </select>
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-800">
                <Button type="button" variant="secondary" onClick={() => setIsModalOpen(false)}>
                  Cancelar
                </Button>
                <Button type="submit" loading={createMutation.isPending}>
                  Criar e Publicar Trilha
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
