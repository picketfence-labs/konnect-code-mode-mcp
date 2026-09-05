/** @type {import('next').NextConfig} */
const nextConfig = {
  // Docker イメージを軽量化するため standalone 出力にする
  output: 'standalone',
  // Kong DP経由で /chat-ui プレフィックス配下に公開する（strip_pathなし）。
  // ビルド時に埋め込まれる値のため、app/page.tsxのAPI呼び出し先と値を揃えること
  basePath: '/chat-ui',
}

module.exports = nextConfig
