import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { ShieldCheck, UserCheck, Lock, CheckCircle2, ArrowRight, Sparkles, MapPin, Phone, Mail, Award } from 'lucide-react'
import api from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'

export function CollaboratorRegisterPage() {
  const navigate = useNavigate()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [cpf, setCpf] = useState('')
  const [phone, setPhone] = useState('')
  const [city, setCity] = useState('')
  const [state, setState] = useState('DF')
  const [radius, setRadius] = useState(30)
  const [termsAccepted, setTermsAccepted] = useState(false)
  
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!termsAccepted) {
      setError('Você deve concordar com os termos de sigilo e tratamento de dados para continuar.')
      return
    }

    setLoading(true)
    try {
      const res = await api.post('/auth/register-collaborator', {
        email,
        password,
        full_name: fullName,
        cpf,
        phone,
        city,
        state,
        operational_radius_km: Number(radius),
      })

      // Store JWT token and redirect to Academy
      localStorage.setItem('operan_token', res.data.access_token)
      navigate('/admin/academy')
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Erro ao realizar cadastro. Verifique os dados e tente novamente.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-xl">
        <div className="text-center mb-8">
          <div className="w-14 h-14 bg-gradient-to-br from-violet-600 to-purple-800 rounded-2xl flex items-center justify-center mx-auto mb-4 border border-white/10 shadow-xl shadow-violet-950/40">
            <ShieldCheck className="w-8 h-8 text-white" />
          </div>
          <span className="text-xs font-bold uppercase tracking-widest text-violet-400 bg-violet-600/20 px-3 py-1 rounded-full">
            Cadastro de Colaborador Operacional
          </span>
          <h1 className="text-3xl font-black text-white mt-3">OPERAN Network</h1>
          <p className="text-gray-400 text-sm mt-1 max-w-md mx-auto">
            Cadastre-se na rede nacional, complete sua capacitação na Academy e receba convocações para fiscalização e operações.
          </p>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-3xl p-8 shadow-2xl">
          {error && (
            <div className="mb-6 p-3.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-medium">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Nome Completo (como consta no documento)"
              placeholder="Ex: João Silva de Souza"
              value={fullName}
              onChange={e => setFullName(e.target.value)}
              required
            />

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label="E-mail"
                type="email"
                placeholder="seu@email.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
              />
              <Input
                label="Senha de Acesso"
                type="password"
                placeholder="Mínimo 6 caracteres"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label="CPF"
                placeholder="000.000.000-00"
                value={cpf}
                onChange={e => setCpf(e.target.value)}
                required
              />
              <Input
                label="WhatsApp / Telefone"
                placeholder="(00) 90000-0000"
                value={phone}
                onChange={e => setPhone(e.target.value)}
                required
              />
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-2">
                <Input
                  label="Cidade de Atuação"
                  placeholder="Ex: Brasília"
                  value={city}
                  onChange={e => setCity(e.target.value)}
                  required
                />
              </div>
              <div>
                <Input
                  label="UF"
                  placeholder="DF"
                  maxLength={2}
                  value={state}
                  onChange={e => setState(e.target.value.toUpperCase())}
                  required
                />
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-gray-300">
                Raio Máximo de Deslocamento para Operações: <strong className="text-violet-400">{radius} km</strong>
              </label>
              <input
                type="range"
                min={10}
                max={150}
                step={10}
                value={radius}
                onChange={e => setRadius(Number(e.target.value))}
                className="w-full accent-violet-600 cursor-pointer"
              />
              <div className="flex justify-between text-xs text-gray-500">
                <span>10 km (Bairro/Centro)</span>
                <span>75 km</span>
                <span>150 km (Região Metropolitana)</span>
              </div>
            </div>

            {/* Caixa de Segurança & LGPD */}
            <div className="p-3.5 rounded-2xl bg-gray-950 border border-gray-800 text-xs text-gray-400 space-y-1.5">
              <div className="flex items-center gap-1.5 text-violet-400 font-semibold">
                <Lock className="w-3.5 h-3.5" />
                <span>Segurança e Criptografia em Repouso</span>
              </div>
              <p>
                Seu CPF, telefone e dados pessoais são criptografados com o padrão bancário AES-256-GCM. Nenhum dado é repassado a terceiros fora das convocações oficiais das bancas organizadoras.
              </p>
            </div>

            <div className="pt-2">
              <label className="flex items-start gap-2.5 text-xs text-gray-400 cursor-pointer">
                <input
                  type="checkbox"
                  checked={termsAccepted}
                  onChange={e => setTermsAccepted(e.target.checked)}
                  className="rounded bg-gray-800 border-gray-700 text-violet-600 focus:ring-violet-500 mt-0.5"
                />
                <span>
                  Declaro que as informações são verídicas e concordo em realizar as formações obrigatórias na <strong>OPERAN Academy</strong> para estar apto à convocação.
                </span>
              </label>
            </div>

            <Button type="submit" loading={loading} size="lg" className="w-full mt-4">
              Concluir Cadastro & Iniciar Formação
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </form>

          <div className="mt-6 text-center text-xs text-gray-500">
            Já possui cadastro na rede?{' '}
            <Link to="/login" className="text-violet-400 hover:text-violet-300 font-medium">
              Fazer login
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
