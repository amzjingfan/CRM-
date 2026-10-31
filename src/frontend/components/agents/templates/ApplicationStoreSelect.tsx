"use client";

import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import type { ApplicationStoreOption } from "../../../lib/agent-templates";

export function ApplicationStoreSelect({ selected, options, search, loading, hasMore, unavailable, disabled, onSearch, onToggle, onLoadMore, onRetry }: {
  selected: ApplicationStoreOption[]; options: ApplicationStoreOption[]; search: string; loading: boolean; hasMore: boolean; unavailable: boolean; disabled: boolean;
  onSearch: (value: string) => void; onToggle: (store: ApplicationStoreOption, checked: boolean) => void; onLoadMore: () => void; onRetry: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [placement, setPlacement] = useState({ above: false, height: 420 });
  const list = useRef<HTMLDivElement>(null); const root = useRef<HTMLDivElement>(null); const trigger = useRef<HTMLButtonElement>(null); const searchInput = useRef<HTMLInputElement>(null);
  const menuId = useId();
  useEffect(() => {
    if (!open) return;
    searchInput.current?.focus();
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    const escape = (event: globalThis.KeyboardEvent) => { if (event.key === "Escape") { event.preventDefault(); setOpen(false); trigger.current?.focus(); } };
    document.addEventListener("pointerdown", outside); document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("pointerdown", outside); document.removeEventListener("keydown", escape); };
  }, [open]);
  useEffect(() => { if (disabled) setOpen(false); }, [disabled]);
  useEffect(() => {
    const viewport = list.current;
    if (open && !loading && !unavailable && hasMore && options.length && viewport && viewport.scrollHeight <= viewport.clientHeight) onLoadMore();
  }, [open, loading, unavailable, hasMore, options.length, onLoadMore]);
  function expand() {
    if (disabled) return;
    const rect = trigger.current?.getBoundingClientRect();
    if (rect) { const below = window.innerHeight - rect.bottom - 16; const above = rect.top - 16; const upwards = below < 280 && above > below; setPlacement({ above: upwards, height: Math.min(420, Math.max(160, upwards ? above : below)) }); }
    setOpen(true);
  }
  function close() { setOpen(false); trigger.current?.focus(); }
  function navigate(event: KeyboardEvent<HTMLDivElement>) {
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    const inputs = Array.from(root.current?.querySelectorAll<HTMLInputElement>('.store-options-scroll input[type="checkbox"]:not(:disabled)') ?? []);
    const index = inputs.indexOf(event.target as HTMLInputElement);
    if (event.target === searchInput.current && event.key === "ArrowDown") { event.preventDefault(); inputs[0]?.focus(); }
    else if (index >= 0) {
      event.preventDefault();
      if (event.key === "ArrowUp" && index === 0) searchInput.current?.focus();
      else inputs[event.key === "Home" ? 0 : event.key === "End" ? inputs.length - 1 : Math.min(inputs.length - 1, index + (event.key === "ArrowDown" ? 1 : -1))]?.focus();
    }
  }
  const names = selected.slice(0, 2).map((store) => store.name).join("、");
  return <div className="field-group application-store-select" ref={root} onBlur={(event) => { if (event.relatedTarget && !event.currentTarget.contains(event.relatedTarget)) setOpen(false); }}>
    <span>选择店铺</span><button aria-label="选择店铺" aria-controls={menuId} aria-expanded={open} aria-haspopup="dialog" role="combobox" className="field store-select-trigger" disabled={disabled} ref={trigger} type="button" onClick={() => open ? close() : expand()} onKeyDown={(event) => { if (event.key === "ArrowDown") { event.preventDefault(); expand(); } }}><span>{selected.length ? `已选 ${selected.length} 店 · ${names}${selected.length > 2 ? "等" : ""}` : "请选择店铺（可多选）"}</span><span aria-hidden="true">⌄</span></button>
    {open ? <div className="store-select-menu" data-above={placement.above} style={{ maxHeight: placement.height }} role="dialog" aria-label="选择授权店铺" id={menuId} onKeyDown={navigate}>
      <label className="store-select-search"><span className="sr-only">搜索店铺</span><input aria-label="搜索店铺" className="field" type="search" placeholder="搜索店铺名称或编码" value={search} ref={searchInput} onChange={(event) => onSearch(event.target.value)} /></label>
      <div className="store-options-scroll" ref={list} onScroll={(event) => { const list = event.currentTarget; if (!loading && hasMore && list.scrollHeight - list.scrollTop - list.clientHeight < 40) onLoadMore(); }}>
        {selected.length ? <div className="store-selected-chips" aria-label="已选店铺">{selected.map((store) => <span key={store.id}>{store.name}<button aria-label={`移除已选店铺 ${store.name}`} type="button" onClick={() => { onToggle(store, false); searchInput.current?.focus(); }}>×</button></span>)}</div> : null}
        <div role="group" aria-label="授权店铺选项">{options.map((store) => <label className="store-select-option" key={store.id}><input type="checkbox" checked={selected.some((item) => item.id === store.id)} onChange={(event) => onToggle(store, event.target.checked)} /> <span>{store.name} · {store.code}</span></label>)}</div>
        {loading ? <p className="help" role="status">正在加载店铺…</p> : unavailable ? <p role="alert">店铺列表暂不可用。<button className="btn small" type="button" onClick={onRetry}>重试加载店铺</button></p> : !options.length ? <p className="help">没有符合条件的可管理店铺。</p> : hasMore ? <p className="help">继续向下滚动加载店铺</p> : <p className="help">已显示全部匹配店铺</p>}
      </div><div className="store-select-footer"><small>已选 {selected.length} 店</small><button className="btn small" type="button" onClick={close}>完成选择</button></div>
    </div> : null}
  </div>;
}
