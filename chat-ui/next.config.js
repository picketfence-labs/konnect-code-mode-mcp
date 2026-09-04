/** @type {import('next').NextConfig} */
const nextConfig = {
  // Docker イメージを軽量化するため standalone 出力にする
  output: 'standalone',
}

module.exports = nextConfig
