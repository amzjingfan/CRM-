"use client";

import { CircleNotch, Tray, WarningCircle } from "@phosphor-icons/react";
import { useLanguage } from "../lib/i18n";

export function LoadingState({ label }: { label?: string }) { const en = useLanguage() === "en"; return <div className="state-box" role="status"><CircleNotch className="state-spinner" size={24} /><p>{label ?? (en ? "Loading…" : "加载中…")}</p></div>; }
export function EmptyState({ label }: { label: string }) { return <div className="state-box" role="status"><span className="state-icon" aria-hidden="true"><Tray size={18} /></span><p>{label}</p></div>; }
export function ErrorState({ message, retry }: { message: string; retry?: () => void }) { const en = useLanguage() === "en"; return <div className="state-box error-state" role="alert"><span className="state-icon" aria-hidden="true"><WarningCircle size={19} /></span><p>{message}</p>{retry ? <button className="text-button mt-3" onClick={retry} type="button">{en ? "Retry" : "重试"}</button> : null}</div>; }
