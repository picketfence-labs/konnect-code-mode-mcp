'use client'

import { useChat } from '@ai-sdk/react'
import { DefaultChatTransport } from 'ai'
import { useState } from 'react'

function partSize(value: unknown): number {
  try {
    return JSON.stringify(value).length
  } catch {
    return 0
  }
}

export default function ChatPage() {
  // basePath（next.config.jsの'/chat-ui'）はnext/linkと違いfetch呼び出し先には
  // 自動で付与されないため、APIパスを明示的に揃える
  const { messages, sendMessage, status } = useChat({
    transport: new DefaultChatTransport({ api: '/chat-ui/api/chat' }),
  })
  const [input, setInput] = useState('')

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim()) return
    sendMessage({ text: input })
    setInput('')
  }

  return (
    <main className="mx-auto flex h-screen max-w-3xl flex-col p-4">
      <header className="mb-4">
        <h1 className="text-xl font-semibold">Context Mesh Chat Demo</h1>
        <p className="text-sm text-slate-500">
          Kong Konnect Context Mesh（Code Mode）経由で、生の12,000件を読まずに集計結果だけを取得します。
        </p>
      </header>

      <div className="flex-1 space-y-4 overflow-y-auto rounded-lg border border-slate-200 bg-white p-4">
        {messages.map((message) => (
          <div key={message.id} className="space-y-2">
            <div className="text-xs font-medium uppercase text-slate-400">
              {message.role === 'user' ? 'あなた' : 'エージェント'}
            </div>
            {message.parts.map((part, i) => {
              if (part.type === 'text') {
                return (
                  <p key={i} className="whitespace-pre-wrap text-slate-800">
                    {part.text}
                  </p>
                )
              }
              // MCP経由のツール（search/get_schema/execute等）は動的ツールとして
              // type: 'dynamic-tool' で届く。静的ツールの 'tool-<name>' とは別扱い
              if (part.type === 'dynamic-tool' || part.type.startsWith('tool-')) {
                const toolPart = part as {
                  type: string
                  toolName?: string
                  toolCallId: string
                  state: string
                  input?: unknown
                  output?: unknown
                }
                const toolName = toolPart.toolName ?? toolPart.type.replace(/^tool-/, '')
                return (
                  <div
                    key={toolPart.toolCallId ?? i}
                    className="rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900"
                  >
                    <span className="font-mono font-semibold">{toolName}</span>
                    {' — '}
                    {toolPart.state}
                    {toolPart.state === 'output-available' && (
                      <span> （応答サイズ: {partSize(toolPart.output)} 文字）</span>
                    )}
                  </div>
                )
              }
              return null
            })}
          </div>
        ))}
      </div>

      <form onSubmit={onSubmit} className="mt-4 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="例: 過去10年の3月の平均気温Top5を教えてください"
          className="flex-1 rounded border border-slate-300 px-3 py-2 text-sm"
          disabled={status === 'streaming' || status === 'submitted'}
        />
        <button
          type="submit"
          className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          disabled={status === 'streaming' || status === 'submitted'}
        >
          送信
        </button>
      </form>
    </main>
  )
}
