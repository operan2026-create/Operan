export function getApiErrorMessage(err: any, fallback = 'Ocorreu um erro inesperado.'): string {
  const detail = err?.response?.data?.detail

  if (typeof detail === 'string' && detail.trim()) return detail

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === 'string') return item
        const field = Array.isArray(item?.loc) ? item.loc.filter((p: unknown) => p !== 'body').join('.') : ''
        const msg = item?.msg || item?.message
        return field && msg ? `${field}: ${msg}` : msg
      })
      .filter(Boolean)

    if (messages.length > 0) return messages.join(' ')
  }

  if (detail && typeof detail === 'object') {
    return detail.msg || detail.message || fallback
  }

  return err?.message || fallback
}
