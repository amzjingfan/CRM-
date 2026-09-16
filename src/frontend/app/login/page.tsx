"use client";

import { FormEvent, useState } from "react";

import { browserLogin } from "../../lib/api";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email || !password) {
      setMessage("请输入邮箱和密码");
      return;
    }
    setIsSubmitting(true);
    setMessage("");
    try {
      await browserLogin(email, password);
      window.location.href = "/workspace";
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "登录失败，请检查邮箱和密码");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="login-canvas">
      <section className="login-shell">
        <div className="login-hero">
          <div className="login-brand"><span className="brand-mark">C</span><span><strong>智能客服</strong><small>CRM SMART SERVICE</small></span></div>
          <div className="login-hero-copy"><p className="eyebrow">ONE SERVICE DESK</p><h1>让每一条客户消息<br />都得到及时回应</h1><p>统一处理 TikTok、Shopee 与 Amazon 会话，用知识库和 AI 建议辅助客服做出可靠判断。</p></div>
          <ul className="login-points"><li><span>01</span>跨平台会话集中处理</li><li><span>02</span>AI 建议始终由人工确认</li><li><span>03</span>权限、店铺与操作全程隔离</li></ul>
        </div>
        <form aria-busy={isSubmitting} className="login-form" onSubmit={handleSubmit}>
          <div className="login-form-heading"><p className="eyebrow">WELCOME BACK</p><h2>登录管理端</h2><p>使用团队账号进入客服工作台</p></div>
          <label className="field-label" htmlFor="email">邮箱<input autoComplete="email" autoFocus className="field" id="email" onChange={(event) => setEmail(event.target.value)} placeholder="name@company.com" type="email" value={email} /></label>
          <label className="field-label" htmlFor="password">密码<input autoComplete="current-password" className="field" id="password" onChange={(event) => setPassword(event.target.value)} placeholder="请输入密码" type="password" value={password} /></label>
          <button className="primary-button w-full" disabled={isSubmitting} type="submit">{isSubmitting ? "正在验证…" : "登录管理端"}</button>
          {message ? <p className="form-message" role="alert">{message}</p> : null}
          <p className="login-footnote">登录即代表你正在访问受权限保护的企业工作区。</p>
        </form>
      </section>
    </main>
  );
}
