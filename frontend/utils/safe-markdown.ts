import MarkdownIt from 'markdown-it'

const BLOCKED_PROTOCOLS = ['javascript:', 'vbscript:', 'data:', 'file:']

const tryDecodeURIComponent = (value: string) => {
  try {
    return decodeURIComponent(value)
  } catch {
    return value
  }
}

const normalizeUrlForCheck = (url: string) =>
  tryDecodeURIComponent(url)
    .replace(/[\u0000-\u001F\u007F\s]+/g, '')
    .toLowerCase()

const hasBlockedProtocol = (url: string) => {
  const normalized = normalizeUrlForCheck(url)
  return BLOCKED_PROTOCOLS.some((protocol) => normalized.startsWith(protocol))
}

export const createSafeMarkdownRenderer = (options?: MarkdownIt.Options) => {
  const md = new MarkdownIt({
    html: false,
    linkify: true,
    breaks: true,
    ...options
  })

  const defaultValidateLink = md.validateLink.bind(md)
  md.validateLink = (url: string) => defaultValidateLink(url) && !hasBlockedProtocol(url)

  const defaultRenderLinkOpen = md.renderer.rules.link_open
  md.renderer.rules.link_open = (tokens, idx, renderOptions, env, self) => {
    const token = tokens[idx]
    const hrefAttrIndex = token.attrIndex('href')
    const href = hrefAttrIndex >= 0 ? (token.attrs?.[hrefAttrIndex]?.[1] ?? '') : ''
    const isExternalLink = /^https?:\/\//i.test(href) || href.startsWith('//')

    token.attrSet('rel', 'noopener noreferrer nofollow')
    if (isExternalLink) {
      token.attrSet('target', '_blank')
    }

    if (defaultRenderLinkOpen) {
      return defaultRenderLinkOpen(tokens, idx, renderOptions, env, self)
    }

    return self.renderToken(tokens, idx, renderOptions)
  }

  return md
}
