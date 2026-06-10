import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 关闭左下角的 Next.js dev 悬浮指示器
  devIndicators: false,

  // dev 模式下允许跨 origin 加载 _next/* 资源（HMR、字体等）
  // trycloudflare 临时隧道域名是随机的，所以用通配符
  allowedDevOrigins: [
    "*.trycloudflare.com",
    "*.serveousercontent.com",
    "127.0.0.1",
    "localhost",
  ],

  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:7860/api/:path*",
      },
    ];
  },
};

export default nextConfig;
