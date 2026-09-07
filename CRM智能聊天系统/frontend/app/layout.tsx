import type { Metadata } from "next";
import "./globals.css";

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
