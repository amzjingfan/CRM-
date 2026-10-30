import type { ReactNode } from "react";

export const fieldLabels: Record<string, string> = {
  name: "名称", code: "编码", agent_type: "Agent 类型", description: "职责描述", model: "模型", model_provider: "模型服务商", model_name: "模型名称", provider: "服务商",
  tool_names: "工具", enabled_tools: "工具", knowledge_slots: "知识需求", knowledge_file_ids: "知识文件", reply_profile: "回复配置", prompt_sections: "提示词",
  identity: "身份", service_scope: "服务范围", tool_rules: "工具规则", escalation: "转人工", language_format: "语言与格式", compliance: "合规", clarification: "澄清",
  "prompt_sections.identity": "身份", "prompt_sections.service_scope": "服务范围", "prompt_sections.tool_rules": "工具规则", "prompt_sections.escalation": "转人工", "prompt_sections.language_format": "语言与格式", "prompt_sections.compliance": "合规", "prompt_sections.clarification": "澄清",
  key: "需求键", purpose: "用途", required: "必需", tone: "语气", reply_language: "回复语言", operator_language: "坐席语言", brand_name: "品牌名称",
};
export const fieldLabel = (field: string) => fieldLabels[field] ?? field;
export function TemplateValue({ value }: { value: unknown }): ReactNode {
  if (value === null || value === undefined) return "未填写";
  if (typeof value === "boolean") return value ? "是" : "否";
  if (typeof value === "string" || typeof value === "number") return String(value) || "空";
  if (Array.isArray(value)) return value.length ? <ul>{value.map((item, index) => <li key={index}><TemplateValue value={item} /></li>)}</ul> : "无";
  if (typeof value === "object") return Object.keys(value).length ? <dl>{Object.entries(value).map(([key, item]) => <div key={key}><dt>{fieldLabel(key)}</dt><dd><TemplateValue value={item} /></dd></div>)}</dl> : "无";
  return "不可显示";
}
