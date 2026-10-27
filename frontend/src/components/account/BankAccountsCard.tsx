import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Landmark, Star, Trash2 } from 'lucide-react'
import api from '../../api/client'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { Input } from '../ui/Input'
import { getApiErrorMessage } from '../../lib/errors'
import type { BankAccount, BankAccountPayload } from '../../types'

const ACCOUNT_TYPES = [
  { value: 'CHECKING', label: 'Conta corrente' },
  { value: 'SAVINGS', label: 'Poupanca' },
  { value: 'PAYMENT', label: 'Conta de pagamento' },
]

const PIX_TYPES = [
  { value: '', label: 'Sem Pix' },
  { value: 'CPF', label: 'CPF' },
  { value: 'CNPJ', label: 'CNPJ' },
  { value: 'EMAIL', label: 'E-mail' },
  { value: 'PHONE', label: 'Telefone' },
  { value: 'RANDOM', label: 'Aleatoria' },
]

const emptyForm: BankAccountPayload = {
  bank_code: '',
  bank_name: '',
  branch: '',
  account_number: '',
  account_type: 'CHECKING',
  holder_name: '',
  holder_cpf: '',
  pix_key_type: '',
  pix_key: '',
  is_primary: false,
}

export function BankAccountsCard() {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<BankAccountPayload>(emptyForm)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const accounts = useQuery({
    queryKey: ['my-bank-accounts'],
    queryFn: () => api.get<BankAccount[]>('/account/bank-accounts').then((r) => r.data),
  })

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['my-bank-accounts'] })

  const create = useMutation({
    mutationFn: () => {
      const payload: BankAccountPayload = {
        ...form,
        holder_cpf: form.holder_cpf || undefined,
        pix_key_type: form.pix_key_type || undefined,
        pix_key: form.pix_key || undefined,
      }
      return api
        .post<BankAccount>('/account/bank-accounts', payload)
        .then((r) => r.data)
    },
    onSuccess: () => {
      setForm(emptyForm)
      setMessage('Conta bancaria salva para validacao.')
      setError('')
      invalidate()
    },
    onError: (err) =>
      setError(getApiErrorMessage(err, 'Nao foi possivel salvar a conta bancaria.')),
  })

  const setPrimary = useMutation({
    mutationFn: (id: string) =>
      api.patch<BankAccount>(`/account/bank-accounts/${id}`, { is_primary: true }),
    onSuccess: () => {
      setMessage('Conta principal atualizada.')
      setError('')
      invalidate()
    },
    onError: (err) =>
      setError(getApiErrorMessage(err, 'Nao foi possivel definir a conta principal.')),
  })

  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/account/bank-accounts/${id}`),
    onSuccess: () => {
      setMessage('Conta bancaria removida.')
      setError('')
      invalidate()
    },
    onError: (err) =>
      setError(getApiErrorMessage(err, 'Nao foi possivel remover a conta bancaria.')),
  })

  const update = (field: keyof BankAccountPayload, value: string | boolean) =>
    setForm((current) => ({ ...current, [field]: value }))

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-white font-bold flex items-center gap-2">
          <Landmark className="w-4 h-4 text-violet-400" />
          Dados bancarios
        </h2>
        <span className="text-[10px] text-gray-500">
          Necessarios apenas para pagamentos
        </span>
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

      {accounts.data?.length ? (
        <ul className="divide-y divide-gray-800 mb-5">
          {accounts.data.map((account) => (
            <li
              key={account.id}
              className="py-3 flex flex-col md:flex-row md:items-center gap-2"
            >
              <div className="min-w-0 flex-1">
                <p className="text-sm text-white flex items-center gap-2">
                  {account.bank_name} - {account.account_number_masked}
                  {account.is_primary && (
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-300 border border-violet-500/20">
                      PRINCIPAL
                    </span>
                  )}
                </p>
                <p className="text-xs text-gray-500">
                  {account.account_type} - {account.holder_name}
                  {account.pix_key_masked ? ` - Pix ${account.pix_key_masked}` : ''}
                </p>
                <p className="text-[10px] text-gray-600 mt-0.5">{account.status}</p>
              </div>
              <div className="flex items-center gap-2">
                {!account.is_primary && (
                  <Button
                    size="sm"
                    variant="secondary"
                    loading={setPrimary.isPending}
                    onClick={() => setPrimary.mutate(account.id)}
                  >
                    <Star className="w-3.5 h-3.5 mr-1" />
                    Principal
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="secondary"
                  loading={remove.isPending}
                  onClick={() => remove.mutate(account.id)}
                >
                  <Trash2 className="w-3.5 h-3.5 mr-1" />
                  Remover
                </Button>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-gray-500 text-sm mb-5">Nenhuma conta bancaria cadastrada.</p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Input
          label="Banco"
          value={form.bank_name}
          onChange={(e) => update('bank_name', e.target.value)}
        />
        <Input
          label="Codigo do banco"
          value={form.bank_code}
          onChange={(e) => update('bank_code', e.target.value)}
        />
        <Input
          label="Agencia"
          value={form.branch}
          onChange={(e) => update('branch', e.target.value)}
        />
        <Input
          label="Conta"
          value={form.account_number}
          onChange={(e) => update('account_number', e.target.value)}
        />
        <div>
          <label className="block text-xs font-semibold text-gray-400 mb-1.5">
            Tipo de conta
          </label>
          <select
            className="w-full bg-gray-950 border border-gray-800 rounded-xl px-3 py-2.5 text-sm text-white"
            value={form.account_type}
            onChange={(e) => update('account_type', e.target.value)}
          >
            {ACCOUNT_TYPES.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
        </div>
        <Input
          label="Titular"
          value={form.holder_name}
          onChange={(e) => update('holder_name', e.target.value)}
        />
        <Input
          label="CPF do titular"
          value={form.holder_cpf || ''}
          onChange={(e) => update('holder_cpf', e.target.value)}
        />
        <div>
          <label className="block text-xs font-semibold text-gray-400 mb-1.5">
            Tipo de chave Pix
          </label>
          <select
            className="w-full bg-gray-950 border border-gray-800 rounded-xl px-3 py-2.5 text-sm text-white"
            value={form.pix_key_type || ''}
            onChange={(e) => update('pix_key_type', e.target.value)}
          >
            {PIX_TYPES.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
        </div>
        {form.pix_key_type && (
          <Input
            label="Chave Pix"
            value={form.pix_key || ''}
            onChange={(e) => update('pix_key', e.target.value)}
          />
        )}
      </div>

      <label className="flex items-center gap-2 mt-4 text-xs text-gray-400">
        <input
          type="checkbox"
          className="accent-violet-600"
          checked={Boolean(form.is_primary)}
          onChange={(e) => update('is_primary', e.target.checked)}
        />
        Usar como conta principal
      </label>

      <Button
        className="mt-4"
        loading={create.isPending}
        disabled={
          !form.bank_code ||
          !form.bank_name ||
          !form.branch ||
          !form.account_number ||
          !form.holder_name ||
          Boolean(form.pix_key_type && !form.pix_key)
        }
        onClick={() => {
          setMessage('')
          setError('')
          create.mutate()
        }}
      >
        Salvar conta bancaria
      </Button>
    </Card>
  )
}
