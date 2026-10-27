import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Trash2, Users } from 'lucide-react'
import api from '../../api/client'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { Input } from '../ui/Input'
import { getApiErrorMessage } from '../../lib/errors'
import type { FamilyMember, FamilyMemberPayload } from '../../types'

const emptyForm: FamilyMemberPayload = {
  full_name: '',
  kinship: '',
  birth_date: '',
  phone: '',
  cpf: '',
  is_legal_guardian: false,
  authorization_reference: '',
  notes: '',
}

export function FamilyMembersCard() {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<FamilyMemberPayload>(emptyForm)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const members = useQuery({
    queryKey: ['my-family-members'],
    queryFn: () => api.get<FamilyMember[]>('/account/family-members').then((r) => r.data),
  })

  const create = useMutation({
    mutationFn: () => {
      const payload: FamilyMemberPayload = {
        ...form,
        birth_date: form.birth_date || undefined,
        phone: form.phone || undefined,
        cpf: form.cpf || undefined,
        authorization_reference: form.authorization_reference || undefined,
        notes: form.notes || undefined,
      }
      return api
        .post<FamilyMember>('/account/family-members', payload)
        .then((r) => r.data)
    },
    onSuccess: () => {
      setForm(emptyForm)
      setMessage('Familiar adicionado.')
      setError('')
      queryClient.invalidateQueries({ queryKey: ['my-family-members'] })
    },
    onError: (err) =>
      setError(getApiErrorMessage(err, 'Nao foi possivel adicionar o familiar.')),
  })

  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/account/family-members/${id}`),
    onSuccess: () => {
      setMessage('Familiar removido.')
      setError('')
      queryClient.invalidateQueries({ queryKey: ['my-family-members'] })
    },
    onError: (err) =>
      setError(getApiErrorMessage(err, 'Nao foi possivel remover o familiar.')),
  })

  const update = (field: keyof FamilyMemberPayload, value: string | boolean) =>
    setForm((current) => ({ ...current, [field]: value }))

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-white font-bold flex items-center gap-2">
          <Users className="w-4 h-4 text-violet-400" />
          Familia e contatos
        </h2>
        <span className="text-[10px] text-gray-500">Dados opcionais</span>
      </div>

      {(message || error) && (
        <div
          className={`mb-4 rounded-lg px-3 py-2 text-xs border ${
            error
              ? 'bg-red-500/10 border-red-500/30 text-red-300'
              : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
          }`}
        >
          {error || message}
        </div>
      )}

      {members.data?.length ? (
        <ul className="divide-y divide-gray-800 mb-5">
          {members.data.map((member) => (
            <li key={member.id} className="py-3 flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm text-white">
                  {member.full_name}
                  {member.is_legal_guardian && (
                    <span className="ml-2 text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                      RESPONSAVEL LEGAL
                    </span>
                  )}
                </p>
                <p className="text-xs text-gray-500">
                  {member.kinship}
                  {member.phone_masked ? ` - ${member.phone_masked}` : ''}
                  {member.cpf_masked ? ` - ${member.cpf_masked}` : ''}
                </p>
              </div>
              <Button
                size="sm"
                variant="secondary"
                loading={remove.isPending}
                onClick={() => remove.mutate(member.id)}
              >
                <Trash2 className="w-3.5 h-3.5 mr-1" />
                Remover
              </Button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-gray-500 text-sm mb-5">Nenhum familiar cadastrado.</p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Input
          label="Nome completo"
          value={form.full_name}
          onChange={(e) => update('full_name', e.target.value)}
        />
        <Input
          label="Parentesco"
          placeholder="Ex: MAE, PAI, CONJUGE"
          value={form.kinship}
          onChange={(e) => update('kinship', e.target.value)}
        />
        <Input
          label="Data de nascimento"
          type="date"
          value={form.birth_date || ''}
          onChange={(e) => update('birth_date', e.target.value)}
        />
        <Input
          label="Telefone"
          value={form.phone || ''}
          onChange={(e) => update('phone', e.target.value)}
        />
        <Input
          label="CPF"
          value={form.cpf || ''}
          onChange={(e) => update('cpf', e.target.value)}
        />
        <Input
          label="Referencia de autorizacao"
          value={form.authorization_reference || ''}
          onChange={(e) => update('authorization_reference', e.target.value)}
        />
      </div>

      <label className="flex items-center gap-2 mt-4 text-xs text-gray-400">
        <input
          type="checkbox"
          className="accent-violet-600"
          checked={Boolean(form.is_legal_guardian)}
          onChange={(e) => update('is_legal_guardian', e.target.checked)}
        />
        E responsavel legal
      </label>

      <Button
        className="mt-4"
        loading={create.isPending}
        disabled={!form.full_name || !form.kinship}
        onClick={() => {
          setMessage('')
          setError('')
          create.mutate()
        }}
      >
        Adicionar familiar
      </Button>
    </Card>
  )
}
