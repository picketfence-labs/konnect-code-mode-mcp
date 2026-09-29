import { createGoogleGenerativeAI } from '@ai-sdk/google'
import { createMCPClient } from '@ai-sdk/mcp'
import { convertToModelMessages, stepCountIs, streamText, type UIMessage } from 'ai'
import { MCP_SERVERS, type MCPServerId } from '../../mcp-servers'

export const maxDuration = 60

type MCPClient = Awaited<ReturnType<typeof createMCPClient>>
type MCPTool = Awaited<ReturnType<MCPClient['tools']>>[string]

const COMMON_PROMPT = `あなたはKong Konnect Context Mesh（Code Mode MCP）デモのAIエージェントです。
接続中のMCPサーバーは、それぞれlist_tools / search / get_schema / executeの4つのmeta-toolを公開します。
質問の内容に合うサーバーのツールだけを使ってください。両方が必要な質問でなければ、もう一方を呼ばないでください。

利用の流れ:
1. 対象サーバーのsearchまたはlist_toolsでAPIツールを探す
2. 同じサーバーのget_schemaで引数を確認する
3. 同じサーバーのexecuteへPythonコードを渡し、\`await call_tool(name, params)\`で実際のAPIを呼ぶ
外側のmeta-tool名にはサーバーの接頭辞が付きますが、call_toolには一覧にある元のAPI Tool名を渡してください。

searchは日本語のクエリでは0件になります。Tool名を_と-で区切った英単語との完全一致で検索してください。
単数形と複数形は別の語として扱われ、camelCaseは分割されません。探しにくければlist_toolsで一覧を確認してください。
execute内のPythonでは、importが失敗する場合があります（Insuranceでは標準ライブラリのimportも失敗します）。importは使わず、dict、list、sorted、sum、roundなどの組み込み機能だけで集計してください。
生のレコードをLLMのコンテキストへ載せず、execute内で取得、ループ、集計、ソートして少数件の結果だけをreturnしてください。`

const WEATHER_PROMPT = `World Weatherの質問にはweather_で始まるmeta-toolを使います。
World WeatherのAPI Tool名はlistCities / getCity / getTemperaturesなどのcamelCaseです。searchよりweather_list_toolsで一覧を見る方が確実です。
例えば「過去10年の3月の平均気温Top5」では、listCitiesで全都市IDを取得し、各都市についてgetTemperaturesをループ呼び出しして3月の気温を集計し、平均値の高い（または低い）上位5件だけをexecute内で算出してreturnしてください。12,000件の生データをコンテキストに載せないでください。`

const INSURANCE_PROMPT = `Insuranceの質問にはinsurance_で始まるmeta-toolを使います。
InsuranceのAPI Tool名は<Source名>_<operationId>のsnake_caseです。例: application_dash_service_list_applications_applications_get、claim_dash_service_list_claims_claims_get、simulation_dash_service_simulate_simulations_post。searchではlist applications、claims、policies、simulateなどの英単語を試してください。
list系の結果は{"total": N, "items": [...]}です。skipとlimitでページングし、limitは最大100です。申込300件や契約200件の集計では、execute内でループして全ページを取得してから集計してください。
デモで使ってよい操作はGET系と、データを変更しないsimulation_dash_service_simulate_simulations_postによる保険料の試算だけです。それ以外のPOST / PUT / DELETEなどの書き込み操作は呼ばないでください。
顧客データは架空でも、マイナンバーに似た値、氏名、住所、電話番号などを含みます。個別の顧客の行や個人を特定できる項目を回答に出さず、集計値だけを返してください。
「商品ごとの申込から契約への成立率」「支払済みの保険金請求額の商品別合計」はInsuranceへの質問です。`

// closeが同期的に例外を投げても、他のclientのcloseを止めない。失敗は握りつぶす
// （例外にはURLが含まれる場合があるため、ログにも出さない）。
async function closeSafely(client: MCPClient): Promise<void> {
  try {
    await client.close()
  } catch {
    // noop
  }
}

function buildSystemPrompt(connectedIds: MCPServerId[]): string {
  return [
    COMMON_PROMPT,
    ...connectedIds.map((id) => id === 'weather' ? WEATHER_PROMPT : INSURANCE_PROMPT),
  ].join('\n\n')
}

export async function POST(req: Request) {
  const { messages }: { messages: UIMessage[] } = await req.json()

  const serverUrls: Record<MCPServerId, string | undefined> = {
    weather: process.env.MCP_WEATHER_URL ?? process.env.MCP_SERVER_URL,
    insurance: process.env.MCP_INSURANCE_URL,
  }
  const configuredServers = MCP_SERVERS.flatMap((server) => {
    const url = serverUrls[server.id]
    return url ? [{ ...server, url }] : []
  })
  if (configuredServers.length === 0) {
    return new Response('MCP_WEATHER_URL（またはMCP_SERVER_URL）かMCP_INSURANCE_URLを設定してください', { status: 500 })
  }

  const connections = await Promise.allSettled(configuredServers.map(async (server) => {
    let client: MCPClient | undefined
    let stage = '接続'
    try {
      client = await createMCPClient({ transport: { type: 'http', url: server.url } })
      stage = 'ツール一覧の取得'
      const tools = await client.tools()
      return { server, client, tools }
    } catch {
      if (client) await closeSafely(client)
      // SDKの例外には接続URLが含まれる場合があるため、ログ用の文言を固定する。
      throw new Error(`MCPの${stage}に失敗しました`)
    }
  }))

  const connected = connections.flatMap((connection) => connection.status === 'fulfilled' ? [connection.value] : [])
  const unavailableIds: MCPServerId[] = []
  connections.forEach((connection, index) => {
    if (connection.status === 'rejected') {
      const server = configuredServers[index]
      unavailableIds.push(server.id)
      console.error(JSON.stringify({
        event: 'mcp_server_unavailable',
        server: server.id,
        message: connection.reason instanceof Error ? connection.reason.message : 'MCPを利用できません',
      }))
    }
  })

  if (connected.length === 0) {
    return new Response('設定済みのMCPサーバーに接続できませんでした', { status: 503 })
  }

  const clients = connected.map(({ client }) => client)
  let closePromise: Promise<void> | undefined
  const closeClients = () => {
    closePromise ??= Promise.all(clients.map(closeSafely)).then(() => undefined)
    return closePromise
  }

  try {
    const tools: Record<string, MCPTool> = {}
    for (const { server, tools: serverTools } of connected) {
      for (const [name, tool] of Object.entries(serverTools)) {
        const key = `${server.id}_${name}`
        if (Object.hasOwn(tools, key)) {
          throw new Error(`MCPツール名が重複しています: ${key}`)
        }
        // 元のToolの execute（元の名前でcallToolするclosure）を保ったまま、説明にServer名を付ける。
        // スプレッドだとTool型のunionが広がるため、Object.assign（交差型）で組み立てる
        tools[key] = Object.assign({}, tool, { description: `[${server.label}] ${tool.description ?? ''}` })
      }
    }

    const google = createGoogleGenerativeAI({ apiKey: process.env.GEMINI_API_KEY })
    const mcpServers = connected.map(({ server }) => server.id)

    const result = streamText({
      model: google(process.env.GEMINI_MODEL ?? 'gemini-3.5-flash'),
      system: buildSystemPrompt(mcpServers),
      messages: await convertToModelMessages(messages),
      tools,
      // meta-toolの探索から実行まで、複数ステップの処理を許す。
      stopWhen: stepCountIs(10),
      onEnd: async (event) => {
        console.log(
          JSON.stringify({
            event: 'chat_completed',
            timestamp: new Date().toISOString(),
            usage: event.usage,
            stepCount: event.steps.length,
            toolCallCount: event.toolCalls.length,
            toolCalls: event.toolCalls.map((call) => call.toolName),
            mcpServers,
            mcpServersUnavailable: unavailableIds,
            finishReason: event.finishReason,
          })
        )
        await closeClients()
      },
    })

    const response = result.toUIMessageStreamResponse()
    if (!response.body) {
      await closeClients()
      return response
    }

    const reader = response.body.getReader()
    const body = new ReadableStream<Uint8Array>({
      async pull(controller) {
        try {
          const { done, value } = await reader.read()
          if (done) {
            controller.close()
            await closeClients()
          } else {
            controller.enqueue(value)
          }
        } catch (error) {
          controller.error(error)
          await closeClients()
        }
      },
      async cancel(reason) {
        try {
          await reader.cancel(reason)
        } finally {
          await closeClients()
        }
      },
    })
    return new Response(body, {
      status: response.status,
      statusText: response.statusText,
      headers: response.headers,
    })
  } catch (error) {
    await closeClients()
    throw error
  }
}
