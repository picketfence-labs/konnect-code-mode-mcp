export const MCP_SERVERS = [
  { id: 'weather', label: 'World Weather' },
  { id: 'insurance', label: 'Insurance' },
] as const

export type MCPServerId = (typeof MCP_SERVERS)[number]['id']
