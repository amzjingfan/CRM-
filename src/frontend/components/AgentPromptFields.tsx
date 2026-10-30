"use client";

export const promptSections = [
  { key: "identity", label: "一、身份与职责边界" },
  { key: "service_scope", label: "二、服务范围（做什么 / 不做什么）" },
  { key: "tool_rules", label: "三、工具使用规则（读宽写严）" },
  { key: "escalation", label: "四、升级触发条件（可观测信号）" },
  { key: "language_format", label: "五、语言与输出格式" },
  { key: "compliance", label: "六、合规红线" },
  { key: "clarification", label: "七、澄清策略与异常兜底" },
] as const;
type ModelOption = { provider: string; model_name: string };
type PromptValue = { model_provider: string | null; model_name: string | null; prompt_sections: Record<string, string> };
const modelKey = (provider: string, name: string) => JSON.stringify([provider, name]);

export function AgentPromptFields({ value, modelOptions, sections = promptSections.map(({ key, label }) => ({ key, title: label })), disabled = false, onChange }: {
  value: PromptValue; modelOptions: ModelOption[]; sections?: { key: string; title: string }[]; disabled?: boolean; onChange: (value: Partial<PromptValue>) => void;
}) {
  const selected = value.model_provider && value.model_name ? modelKey(value.model_provider, value.model_name) : "";
  const configured = modelOptions.some((option) => modelKey(option.provider, option.model_name) === selected);
  return <>
    <div className="model-section"><label className="field-group"><span>驱动模型 · 已接入</span><select className="field model-select" disabled={disabled} value={selected} onChange={(event) => {
      const option = modelOptions.find((item) => modelKey(item.provider, item.model_name) === event.target.value);
      onChange({ model_provider: option?.provider ?? null, model_name: option?.model_name ?? null });
    }}><option value="">请选择已配置模型</option>{selected && !configured ? <option value={selected} disabled>{value.model_provider} / {value.model_name}（草稿保留，当前未配置）</option> : null}{modelOptions.map((option) => <option value={modelKey(option.provider, option.model_name)} key={modelKey(option.provider, option.model_name)}>{option.provider} / {option.model_name}</option>)}</select></label><p className="model-help">已发布版本冻结模型配置；草稿修改不会改变正在运行的版本。</p></div>
    <div className="prompt-section"><h4>七段式系统提示词 · {disabled ? "只读" : "可编辑"}</h4>{sections.map((section) => <label className="field-group wide" key={section.key}><span>{section.title}</span><textarea className="field fieldarea" aria-label={section.title} disabled={disabled} maxLength={4000} value={value.prompt_sections[section.key] ?? ""} onChange={(event) => onChange({ prompt_sections: { ...value.prompt_sections, [section.key]: event.target.value } })} /></label>)}<p className="prompt-help">七段均必填。平台安全边界由服务端固定，运营提示词不能扩大权限或开启自动发送。</p></div>
  </>;
}
