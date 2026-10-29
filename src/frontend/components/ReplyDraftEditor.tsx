"use client";

import { useId, useRef } from "react";
import { ArrowsOutSimple, X } from "@phosphor-icons/react";

type Props = {
  draft: string;
  en: boolean;
  disabled: boolean;
  limit: number;
  translation?: string;
  onChange: (value: string) => void;
};

export function ReplyDraftEditor({ draft, en, disabled, limit, translation, onChange }: Props) {
  const dialogRef = useRef<HTMLDialogElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const editorRef = useRef<HTMLTextAreaElement | null>(null);
  const descriptionId = useId();
  const limitId = useId();
  const oversized = draft.length > limit;

  function openEditor() {
    const dialog = dialogRef.current;
    const editor = editorRef.current;
    if (!dialog || !editor) return;
    dialog.showModal();
    editor.focus();
    editor.setSelectionRange(0, 0);
    editor.scrollTop = 0;
  }

  return <>
    <button aria-haspopup="dialog" className="workspace-toolbar-button workspace-expand-editor" disabled={disabled} onClick={openEditor} ref={triggerRef} type="button"><ArrowsOutSimple aria-hidden="true" size={16} />{en ? "Expand editor" : "展开编辑"}</button>
    <dialog aria-label={en ? "Full reply editor" : "完整回复编辑"} className="action-dialog workspace-draft-editor" onClose={() => triggerRef.current?.focus()} ref={dialogRef}>
      <header className="workspace-draft-editor-heading"><h2>{en ? "Full reply editor" : "完整回复编辑"}</h2><button aria-label={en ? "Close editor" : "关闭编辑"} className="workspace-draft-editor-close" onClick={() => dialogRef.current?.close()} type="button"><X aria-hidden="true" size={20} /></button></header>
      <p id={descriptionId}>{en ? "Changes are kept automatically. Enter adds a new line. Close this window to review and send from the composer." : "编辑自动保留，Enter 换行。关闭后回到发送栏审阅和发送。"}</p>
      <label className="workspace-draft-editor-field"><span>{en ? "Complete draft" : "完整草稿"}</span><textarea aria-describedby={`${descriptionId} ${limitId}`} onChange={(event) => onChange(event.target.value)} ref={editorRef} value={draft} /></label>
      {translation ? <details className="workspace-draft-editor-preview"><summary>{en ? "Full translation preview" : "完整译文预览"}</summary><p aria-label={en ? "Complete translation" : "完整译文"}>{translation}</p></details> : null}
      <footer className="workspace-draft-editor-footer"><p className="workspace-draft-limit" id={limitId} role={oversized ? "alert" : "status"}>{draft.length}/{limit}{oversized ? (en ? ` · Exceeds ${limit} characters; shorten before review or sending.` : ` · 超过 ${limit} 字，请精简后再审阅发送。`) : ""}</p><button className="primary-button" onClick={() => dialogRef.current?.close()} type="button">{en ? "Done editing" : "完成编辑"}</button></footer>
    </dialog>
  </>;
}
