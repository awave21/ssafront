/**
 * Universal cURL command parser.
 * Handles: multiple -d, --get/-G, form-encoded data, JSON body,
 * query params, combined short flags, backtick comments, etc.
 */

export type ParsedCurlParam = {
  key: string
  value: string
  location: 'query' | 'body'
}

export type ParsedCurl = {
  url: string
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  headers: Record<string, string>
  body: string | null
  bodyJson: Record<string, any> | null
  queryParams: ParsedCurlParam[]
  bodyParams: ParsedCurlParam[]
  authType: 'none' | 'api_key' | 'oauth2' | 'service'
  authValue: string | null
}

// ─── Tokenizer ───────────────────────────────────────────────────────

/**
 * Tokenize a cURL command string, respecting quotes and escapes.
 * - Removes line continuations (\↵)
 * - Strips backtick-wrapped comments (`# ...`)
 * - Handles single/double/$'...' quoting
 */
const tokenize = (input: string): string[] => {
  // Strip backtick-wrapped comments like `# Filters`
  let cleaned = input.replace(/`[^`]*`/g, '')

  // Remove line continuations (backslash + optional whitespace + newline)
  cleaned = cleaned
    .replace(/\\\s*\r?\n/g, ' ')
    .replace(/\r?\n/g, ' ')
    .trim()

  const tokens: string[] = []
  let current = ''
  let i = 0

  const flush = () => {
    if (current.length > 0) {
      tokens.push(current)
      current = ''
    }
  }

  while (i < cleaned.length) {
    const ch = cleaned[i]

    // Whitespace → flush token
    if (ch === ' ' || ch === '\t') {
      flush()
      i++
      continue
    }

    // Double-quoted string
    if (ch === '"') {
      i++
      while (i < cleaned.length && cleaned[i] !== '"') {
        if (cleaned[i] === '\\' && i + 1 < cleaned.length) {
          const next = cleaned[i + 1]
          if ('"\\$`'.includes(next)) {
            current += next
            i += 2
          } else {
            current += cleaned[i]
            i++
          }
        } else {
          current += cleaned[i]
          i++
        }
      }
      i++ // skip closing "
      continue
    }

    // Single-quoted string (no escaping)
    if (ch === '\'') {
      i++
      while (i < cleaned.length && cleaned[i] !== '\'') {
        current += cleaned[i]
        i++
      }
      i++
      continue
    }

    // $'...' ANSI-C quoting
    if (ch === '$' && i + 1 < cleaned.length && cleaned[i + 1] === '\'') {
      i += 2
      while (i < cleaned.length && cleaned[i] !== '\'') {
        if (cleaned[i] === '\\' && i + 1 < cleaned.length) {
          const esc = cleaned[i + 1]
          const escMap: Record<string, string> = { n: '\n', t: '\t', r: '\r', '\\': '\\', '\'': '\'' }
          if (escMap[esc]) { current += escMap[esc]; i += 2 }
          else { current += cleaned[i]; i++ }
        } else {
          current += cleaned[i]
          i++
        }
      }
      i++
      continue
    }

    // Backslash escape outside quotes
    if (ch === '\\' && i + 1 < cleaned.length) {
      current += cleaned[i + 1]
      i += 2
      continue
    }

    current += ch
    i++
  }

  flush()
  return tokens
}

// ─── Helpers ─────────────────────────────────────────────────────────

/** Decode URL-encoded string (+ → space, %XX) */
const urlDecode = (s: string): string => {
  try {
    return decodeURIComponent(s.replace(/\+/g, ' '))
  } catch {
    return s.replace(/\+/g, ' ')
  }
}

/** Parse form-encoded string (key=value&key2=value2) into pairs */
const parseFormEncoded = (str: string): Array<{ key: string; value: string }> => {
  return str.split('&').filter(Boolean).map(pair => {
    const eqIdx = pair.indexOf('=')
    if (eqIdx === -1) return { key: urlDecode(pair), value: '' }
    return {
      key: urlDecode(pair.slice(0, eqIdx)),
      value: urlDecode(pair.slice(eqIdx + 1))
    }
  })
}

/** Extract query string from URL, return clean URL + params */
const extractQueryFromUrl = (rawUrl: string): { cleanUrl: string; params: Array<{ key: string; value: string }> } => {
  const qIdx = rawUrl.indexOf('?')
  if (qIdx === -1) return { cleanUrl: rawUrl, params: [] }
  return {
    cleanUrl: rawUrl.slice(0, qIdx),
    params: parseFormEncoded(rawUrl.slice(qIdx + 1))
  }
}

/** Detect auth type from headers */
const detectAuth = (headers: Record<string, string>): { type: ParsedCurl['authType']; value: string | null } => {
  const entry = Object.entries(headers).find(([k]) => k.toLowerCase() === 'authorization')
  if (!entry) return { type: 'none', value: null }

  const val = entry[1]
  if (val.toLowerCase().startsWith('bearer ')) return { type: 'api_key', value: val.slice(7) }
  if (val.toLowerCase().startsWith('basic ')) return { type: 'api_key', value: val }
  return { type: 'api_key', value: val }
}

/** Check if string looks like JSON */
const isJsonLike = (s: string): boolean => {
  const trimmed = s.trim()
  return (trimmed.startsWith('{') && trimmed.endsWith('}')) ||
         (trimmed.startsWith('[') && trimmed.endsWith(']'))
}

// ─── Known flags ─────────────────────────────────────────────────────

/** Flags that take no value (booleans) */
const BOOLEAN_FLAGS = new Set([
  '-G', '--get',
  '-k', '--insecure',
  '-L', '--location',
  '-s', '--silent',
  '-S', '--show-error',
  '-v', '--verbose',
  '-i', '--include',
  '-I', '--head',
  '-g', '--globoff',
  '-N', '--no-buffer',
  '-f', '--fail',
  '-n', '--netrc',
  '--compressed',
  '--tr-encoding',
  '--raw',
  '--tcp-nodelay',
  '--http1.0', '--http1.1', '--http2',
])

/** Flags that consume one argument (value flags we want to skip) */
const SKIP_VALUE_FLAGS = new Set([
  '-o', '--output',
  '-w', '--write-out',
  '--connect-timeout', '--max-time', '-m',
  '--retry', '--retry-delay', '--retry-max-time',
  '--cacert', '--capath', '--cert', '--key',
  '-e', '--referer',
  '--cookie', '-b', '--cookie-jar', '-c',
  '--resolve', '--interface',
  '-x', '--proxy', '--proxy-user',
  '--ciphers', '--tlsv1.2', '--tls-max',
  '-F', '--form',
])

// ─── Main parser ─────────────────────────────────────────────────────

export const parseCurl = (curlString: string): ParsedCurl => {
  const tokens = tokenize(curlString)

  let url = ''
  let explicitMethod: string | null = null
  let isGet = false // --get / -G flag
  let isHead = false
  const headers: Record<string, string> = {}
  const dataChunks: string[] = [] // all -d values collected
  let basicAuth: string | null = null
  let userAgent: string | null = null

  let i = 0

  // Skip 'curl' if first token
  if (tokens.length > 0 && tokens[0].toLowerCase() === 'curl') {
    i = 1
  }

  while (i < tokens.length) {
    const token = tokens[i]

    // ── Method: -X / --request ──
    if ((token === '-X' || token === '--request') && i + 1 < tokens.length) {
      explicitMethod = tokens[i + 1]
      i += 2
      continue
    }

    // ── Header: -H / --header ──
    if ((token === '-H' || token === '--header') && i + 1 < tokens.length) {
      const hdr = tokens[i + 1]
      const colonIdx = hdr.indexOf(':')
      if (colonIdx > 0) {
        headers[hdr.slice(0, colonIdx).trim()] = hdr.slice(colonIdx + 1).trim()
      }
      i += 2
      continue
    }

    // ── Data: -d / --data / --data-raw / --data-binary / --data-urlencode ──
    if (
      (token === '-d' || token === '--data' || token === '--data-raw' ||
       token === '--data-binary' || token === '--data-urlencode') &&
      i + 1 < tokens.length
    ) {
      dataChunks.push(tokens[i + 1])
      i += 2
      continue
    }

    // ── Basic auth: -u / --user ──
    if ((token === '-u' || token === '--user') && i + 1 < tokens.length) {
      basicAuth = tokens[i + 1]
      i += 2
      continue
    }

    // ── User-Agent: -A / --user-agent ──
    if ((token === '-A' || token === '--user-agent') && i + 1 < tokens.length) {
      userAgent = tokens[i + 1]
      i += 2
      continue
    }

    // ── Boolean flags ──
    if (BOOLEAN_FLAGS.has(token)) {
      if (token === '-G' || token === '--get') isGet = true
      if (token === '-I' || token === '--head') isHead = true
      i++
      continue
    }

    // ── Combined short flags: -sSLk, -kGv, etc. ──
    if (token.startsWith('-') && !token.startsWith('--') && token.length > 2) {
      // Check if ALL characters are known boolean short flags
      const chars = token.slice(1).split('')
      const allBoolean = chars.every(c => BOOLEAN_FLAGS.has(`-${c}`))
      if (allBoolean) {
        chars.forEach(c => {
          if (c === 'G') isGet = true
          if (c === 'I') isHead = true
        })
        i++
        continue
      }
    }

    // ── Skip-value flags ──
    if (SKIP_VALUE_FLAGS.has(token) && i + 1 < tokens.length) {
      i += 2
      continue
    }

    // ── URL: anything that doesn't start with - ──
    if (!token.startsWith('-') && !url) {
      url = token
      i++
      continue
    }

    // Unknown — skip
    i++
  }

  // Apply user-agent
  if (userAgent) headers['User-Agent'] = userAgent

  // Apply basic auth as Authorization header
  if (basicAuth) {
    const encoded = typeof btoa !== 'undefined'
      ? btoa(basicAuth)
      : Buffer.from(basicAuth).toString('base64')
    headers['Authorization'] = `Basic ${encoded}`
  }

  // ── Determine method ──
  let method: ParsedCurl['method']
  if (explicitMethod) {
    const upper = explicitMethod.toUpperCase()
    method = (['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].includes(upper)
      ? upper : 'GET') as ParsedCurl['method']
  } else if (isHead) {
    method = 'GET'
  } else if (isGet) {
    method = 'GET'
  } else if (dataChunks.length > 0) {
    method = 'POST'
  } else {
    method = 'GET'
  }

  // ── Extract query params from URL ──
  const { cleanUrl, params: urlQueryParams } = extractQueryFromUrl(url)
  url = cleanUrl

  // ── Process -d chunks ──
  const queryParams: ParsedCurlParam[] = urlQueryParams.map(p => ({ ...p, location: 'query' as const }))
  const bodyParams: ParsedCurlParam[] = []
  let body: string | null = null
  let bodyJson: Record<string, any> | null = null

  if (dataChunks.length > 0) {
    if (isGet) {
      // --get flag: ALL -d values become query parameters
      dataChunks.forEach(chunk => {
        parseFormEncoded(chunk).forEach(p => {
          queryParams.push({ key: p.key, value: p.value, location: 'query' })
        })
      })
    } else if (dataChunks.length === 1 && isJsonLike(dataChunks[0])) {
      // Single JSON body
      body = dataChunks[0]
      try {
        bodyJson = JSON.parse(body)
      } catch {
        bodyJson = null
      }
    } else if (dataChunks.length === 1 && dataChunks[0].includes('=')) {
      // Single form-encoded string: key=val&key2=val2
      body = dataChunks[0]
      parseFormEncoded(body).forEach(p => {
        bodyParams.push({ key: p.key, value: p.value, location: 'body' })
      })
    } else if (dataChunks.length > 1) {
      // Multiple -d flags → each is a form param (key=value)
      dataChunks.forEach(chunk => {
        const eqIdx = chunk.indexOf('=')
        if (eqIdx > 0) {
          bodyParams.push({
            key: urlDecode(chunk.slice(0, eqIdx)),
            value: urlDecode(chunk.slice(eqIdx + 1)),
            location: 'body'
          })
        } else {
          bodyParams.push({ key: urlDecode(chunk), value: '', location: 'body' })
        }
      })
      body = dataChunks.join('&')
    } else {
      // Fallback: raw body
      body = dataChunks[0]
    }
  }

  // If --get and we have bodyParams, move them to query
  if (isGet && bodyParams.length > 0) {
    bodyParams.forEach(p => queryParams.push({ ...p, location: 'query' }))
    bodyParams.length = 0
  }

  const auth = detectAuth(headers)

  return {
    url,
    method,
    headers,
    body,
    bodyJson,
    queryParams,
    bodyParams,
    authType: auth.type,
    authValue: auth.value
  }
}
