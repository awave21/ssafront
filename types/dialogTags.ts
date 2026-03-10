export type DialogTag = {
  tag: string
  source: string
  confidence?: number | null
  metadata?: Record<string, any> | null
  created_at: string
}
