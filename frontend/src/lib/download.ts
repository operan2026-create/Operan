import api from '../api/client'

export async function downloadDocument(path: string, fileName?: string) {
  const relative = path.replace(/^\/api\/v1/, '')
  const response = await api.get(relative, { responseType: 'blob' })
  const url = URL.createObjectURL(response.data)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = fileName || 'documento'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
