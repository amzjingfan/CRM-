import type { Metadata } from "next";
import "./globals.css";

// 管理端 HTML 每次获取当前版本；带指纹的静态资源仍由 Next.js 独立缓存。
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "CRM 智能聊天系统",
  description: "跨境电商智能客服平台",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
