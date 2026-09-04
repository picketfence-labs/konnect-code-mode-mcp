import { createGoogleGenerativeAI } from '@ai-sdk/google'
import { createMCPClient } from '@ai-sdk/mcp'
import { convertToModelMessages, stepCountIs, streamText, type UIMessage } from 'ai'

export const maxDuration = 60

const SYSTEM_PROMPT = `あなたはKong Konnect Context Mesh（Code Mode MCP）デモのAIエージェントです。
接続先のMCPサーバーは "search" / "get_schema" / "execute" / "list_tools" の4ツールのみを
公開しています。これはCode Modeという仕組みで、実際にデータを取得・加工するAPI
（listCities / getCity / getTemperatures 等）はサンドボックス内Pythonコードから
呼び出すことで、生のレコードをあなた（LLM）に直接見せずに済むようにしています。

利用の流れ:
1. "search" で目的に合うAPIツールを見つける
2. "get_schema" でそのツールの引数スキーマを確認する
3. "execute" にPythonコードを渡し、\`await call_tool(name, params)\`でAPIを呼び出し、
   ループ・集計・ソートなどの加工をサンドボックス内で行ってから \`return\` で
   最終結果（少数件）だけを返す

例えば「過去10年の3月の平均気温Top5」のような質問では、\`listCities\`で全都市IDを取得し、
各都市について\`getTemperatures\`をループ呼び出しして3月の気温を集計し、平均値の高い
（または低い）上位5件だけをexecute内で算出してreturnすること。12,000件の生データを
そのままあなたのコンテキストに載せないことが、このデモの核心的な価値提示です。`

export async function POST(req: Request) {
  const { messages }: { messages: UIMessage[] } = await req.json()

  const mcpServerUrl = process.env.MCP_SERVER_URL
  if (!mcpServerUrl) {
    return new Response('MCP_SERVER_URL is not configured', { status: 500 })
  }

  const mcpClient = await createMCPClient({
    transport: { type: 'http', url: mcpServerUrl },
  })

  try {
    const tools = await mcpClient.tools()

    const google = createGoogleGenerativeAI({ apiKey: process.env.GEMINI_API_KEY })

    const result = streamText({
      model: google(process.env.GEMINI_MODEL ?? 'gemini-3.5-flash'),
      system: SYSTEM_PROMPT,
      messages: await convertToModelMessages(messages),
      tools,
      // search→get_schema→execute の複数ステップを跨いで最終テキスト回答に到達させる
      stopWhen: stepCountIs(10),
      onFinish: async () => {
        await mcpClient.close()
      },
    })

    return result.toUIMessageStreamResponse()
  } catch (error) {
    await mcpClient.close()
    throw error
  }
}
