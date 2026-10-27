export const PROFESSIONAL_FUNCTIONS = [
  { value: 'FISCAL_SALA', label: 'Fiscal de Sala' },
  { value: 'VOLANTE', label: 'Volante' },
  { value: 'CHEFE_SALA', label: 'Chefe de Sala' },
  { value: 'APOIO', label: 'Apoio' },
  { value: 'SUPERVISOR', label: 'Supervisor' },
  { value: 'FISCAL_BANHEIRO', label: 'Fiscal de Banheiro' },
  { value: 'COORDENADOR', label: 'Coordenador' },
] as const

export function professionalFunctionLabel(value?: string): string {
  return PROFESSIONAL_FUNCTIONS.find((item) => item.value === value)?.label ?? value ?? '-'
}
