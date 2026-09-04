# Context Mesh デモ用 Chat UI（Next.js + Vercel AI SDK + MCP client）
# multi-stage: 依存インストール → ビルド → standalone実行時イメージ

FROM node:20-slim AS deps
WORKDIR /app
COPY package.json ./
RUN npm install

FROM node:20-slim AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production
# next.config.js の output: 'standalone' が生成する最小限のランタイムのみコピー
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public

EXPOSE 3000
# 0.0.0.0 で待受（クラスタ内 Service から到達可能に）
ENV HOSTNAME=0.0.0.0
CMD ["node", "server.js"]
