import type { MessageView } from "./api";

type Role = MessageView["role"];

export const senderLabel = (role: Role, en: boolean): string => ({
  user: en ? "Buyer" : "买家",
  agent: en ? "Customer service" : "客服",
  assistant: en ? "Robot" : "机器人",
  system: en ? "System" : "系统",
}[role]);

export const messageSide = (role: Role): "incoming" | "outgoing" | "system" =>
  role === "user" ? "incoming" : role === "system" ? "system" : "outgoing";

export const buyerAvatarText = (name: string | null): string =>
  Array.from(name?.trim() ?? "").slice(0, 3).join("").toUpperCase() || "?";
