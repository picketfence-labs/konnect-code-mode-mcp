import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Context Mesh Chat Demo',
  description: 'Kong Konnect Context Mesh (Code Mode MCP) デモ用 Chat UI',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  )
}
