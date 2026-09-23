"use client";

import Link from "next/link";
import {
  Archive,
  ArrowClockwise,
  BookOpenText,
  CheckCircle,
  FileText,
  FolderOpen,
  FolderSimple,
  Lightbulb,
  MagnifyingGlass,
  PencilSimple,
  Plus,
  Stack,
  Trash,
  UploadSimple,
  X,
} from "@phosphor-icons/react";
import { FormEvent, type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import {
  archiveKnowledgeEntry,
  createKnowledgeCategory,
  createKnowledgeEntry,
  currentUser,
  deleteKnowledgeCategory,
  deleteKnowledgeEntry,
  getImportJob,
  getKnowledgeVectorizationStatus,
  importKnowledge,
  isAuthenticationError,
  listKnowledgeCategories,
  listKnowledgeEntries,
  publishKnowledgeEntry,
  retryKnowledgeVectorization,
  updateKnowledgeCategory,
  updateKnowledgeEntry,
  type ImportJob,
  type KnowledgeCategory,
  type KnowledgeCustomerScope,
  type KnowledgeEntry,
  type KnowledgeStatementType,
  type KnowledgeVectorizationStatus,
} from "../../lib/api";
import { useLanguage } from "../../lib/i18n";

type CategoryTreeItem = KnowledgeCategory & { depth: number };
type KnowledgeLayer = "A" | "B" | "C" | "D";

const knowledgeLayers: Array<{ key: KnowledgeLayer; zh: string; en: string }> = [
  { key: "A", zh: "A层 · 原始数据", en: "Layer A · Sources" },
  { key: "B", zh: "B层 · 业务规则", en: "Layer B · Rules" },
  { key: "C", zh: "C层 · FAQ 问答", en: "Layer C · FAQ" },
  { key: "D", zh: "D层 · 案例库", en: "Layer D · Cases" },
];

const statementTypes: Array<{ value: KnowledgeStatementType; zh: string; en: string }> = [
  { value: "unknown", zh: "未分类（不可发布）", en: "Unknown (cannot publish)" },
  { value: "policy", zh: "通用政策", en: "Policy" },
  { value: "technical_artifact", zh: "技术资产", en: "Technical artifact" },
  { value: "non_assertive_proposition", zh: "非断言命题", en: "Non-assertive proposition" },
  { value: "customer_instance_fact", zh: "客户实例事实", en: "Customer instance fact" },
];

const customerScopes: Array<{ value: KnowledgeCustomerScope; zh: string; en: string }> = [
  { value: "none", zh: "不涉及客户", en: "No customer scope" },
  { value: "generic", zh: "通用客户范围", en: "Generic customer scope" },
  { value: "specific_customer", zh: "具体客户", en: "Specific customer" },
];

function flattenCategoryTree(categories: KnowledgeCategory[]): CategoryTreeItem[] {
  const children = new Map<string | null, KnowledgeCategory[]>();
  for (const category of categories) {
    const siblings = children.get(category.parent_id) ?? [];
    siblings.push(category);
    children.set(category.parent_id, siblings);
  }
  for (const siblings of children.values()) siblings.sort((left, right) => left.sort_order - right.sort_order || left.name.localeCompare(right.name));

  const result: CategoryTreeItem[] = [];
  const visited = new Set<string>();
  const visit = (parentId: string | null, depth: number) => {
    for (const category of children.get(parentId) ?? []) {
      if (visited.has(category.id)) continue;
      visited.add(category.id);
      result.push({ ...category, depth });
      visit(category.id, depth + 1);
    }
  };
  visit(null, 0);

  // 父节点异常或不在当前店铺结果集时仍展示条目，避免运营人员误以为分类已丢失。
  for (const category of categories) if (!visited.has(category.id)) result.push({ ...category, depth: 0 });
  return result;
}

function collectDescendantIds(categories: KnowledgeCategory[], categoryId: string): Set<string> {
  const blocked = new Set<string>([categoryId]);
  let changed = true;
  while (changed) {
    changed = false;
    for (const category of categories) {
      if (category.parent_id && blocked.has(category.parent_id) && !blocked.has(category.id)) {
        blocked.add(category.id);
        changed = true;
      }
    }
  }
  return blocked;
}

function layerKey(layer: string): KnowledgeLayer {
  const normalized = layer.trim().toUpperCase();
  if (normalized.startsWith("A") || normalized.includes("RAW") || normalized.includes("SOURCE")) return "A";
  if (normalized.startsWith("B") || normalized.includes("RULE")) return "B";
  if (normalized.startsWith("D") || normalized.includes("CASE")) return "D";
  return "C";
}

function parseKnowledgeLayer(value: string | null): KnowledgeLayer | "" {
  return knowledgeLayers.some((layer) => layer.key === value) ? value as KnowledgeLayer : "";
}

function statusText(status: string, en: boolean) {
  const labels: Record<string, [string, string]> = {
    draft: ["草稿", "Draft"], published: ["已发布", "Published"], archived: ["已归档", "Archived"],
    pending: ["待向量化", "Pending"], processing: ["向量化中", "Processing"], ready: ["向量就绪", "Ready"], failed: ["向量失败", "Failed"],
  };
  return labels[status]?.[en ? 1 : 0] ?? status;
}

export default function KnowledgePage() {
  const en = useLanguage() === "en";
  const [storeId, setStoreId] = useState("");
  const [stores, setStores] = useState<string[]>([]);
  const [categories, setCategories] = useState<KnowledgeCategory[]>([]);
  const [entries, setEntries] = useState<KnowledgeEntry[]>([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState("");
  const [selectedLayer, setSelectedLayer] = useState<KnowledgeLayer | "">("");
  const [vectorizationStatus, setVectorizationStatus] = useState<KnowledgeVectorizationStatus | null>(null);
  const [retryingEntryId, setRetryingEntryId] = useState<string | null>(null);
  const [search, setSearch] = useState(""); const [status, setStatus] = useState(""); const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [job, setJob] = useState<ImportJob | null>(null);
  const [editingCategory, setEditingCategory] = useState<KnowledgeCategory | null>(null);
  const [editingEntry, setEditingEntry] = useState<KnowledgeEntry | null>(null);
  const [categoryEditorOpen, setCategoryEditorOpen] = useState(false);
  const [entryEditorOpen, setEntryEditorOpen] = useState(false);
  const [categorySubmitting, setCategorySubmitting] = useState(false);
  const [entrySubmitting, setEntrySubmitting] = useState(false);
  const loadRequestId = useRef(0);

  const categoryTree = useMemo(() => flattenCategoryTree(categories), [categories]);
  const selectedCategory = categories.find((category) => category.id === selectedCategoryId) ?? null;
  const selectedLayerLabel = knowledgeLayers.find((layer) => layer.key === selectedLayer);
  const selectedScopeLabel = selectedCategory?.name ?? (selectedLayerLabel ? (en ? selectedLayerLabel.en : selectedLayerLabel.zh) : (en ? "All knowledge" : "全部知识"));
  const blockedParentIds = useMemo(() => editingCategory ? collectDescendantIds(categories, editingCategory.id) : new Set<string>(), [categories, editingCategory]);
  const categoriesByLayer = useMemo(() => {
    const groups = new Map<KnowledgeLayer, CategoryTreeItem[]>(knowledgeLayers.map((layer) => [layer.key, []]));
    for (const category of categoryTree) groups.get(layerKey(category.layer))?.push(category);
    return groups;
  }, [categoryTree]);

  const load = useCallback(async () => {
    if (!storeId) return;
    const requestId = ++loadRequestId.current;
    setLoading(true);
    setError("");
    try {
      const query = new URLSearchParams({ page: String(page), page_size: "20", store_id: storeId });
      if (search) query.set("search", search);
      if (status) query.set("status", status);
      if (selectedCategoryId) query.set("category_id", selectedCategoryId);
      else if (selectedLayer) query.set("layer", selectedLayer);
      const [categoryData, entryData, vectorData] = await Promise.all([
        listKnowledgeCategories(storeId),
        listKnowledgeEntries(query),
        getKnowledgeVectorizationStatus(storeId),
      ]);
      // 快速切换层级或分类时，只允许最后一次请求更新列表，避免旧响应覆盖当前选择。
      if (requestId !== loadRequestId.current) return;
      setCategories(categoryData);
      setEntries(entryData.items);
      setTotal(entryData.total);
      setVectorizationStatus(vectorData);
    } catch (caught) {
      if (requestId !== loadRequestId.current) return;
      setError(caught instanceof Error ? caught.message : (en ? "Knowledge loading failed" : "知识库加载失败"));
    } finally {
      if (requestId === loadRequestId.current) setLoading(false);
    }
  }, [en, page, search, selectedCategoryId, selectedLayer, status, storeId]);

  useEffect(() => {
    void currentUser().then((user) => {
      const params = new URLSearchParams(window.location.search);
      setStores(user.store_ids);
      const requestedStoreId = params.get("store_id");
      const nextStoreId = requestedStoreId && user.store_ids.includes(requestedStoreId) ? requestedStoreId : user.store_ids[0] ?? "";
      setStoreId(nextStoreId);
      if (!nextStoreId) setLoading(false);
      setSearch(params.get("search") ?? "");
      setStatus(params.get("status") ?? "");
      const categoryId = params.get("category_id") ?? "";
      setSelectedCategoryId(categoryId);
      setSelectedLayer(categoryId ? "" : parseKnowledgeLayer(params.get("layer")));
      setPage(Number(params.get("page") || 1));
    }).catch((caught: unknown) => {
      if (!isAuthenticationError(caught)) {
        setError(caught instanceof Error ? caught.message : (en ? "User loading failed" : "用户信息加载失败"));
        setLoading(false);
      }
    });
  }, [en]);

  useEffect(() => () => { loadRequestId.current += 1; }, []);

  useEffect(() => {
    if (!storeId) return;
    const params = new URLSearchParams({ store_id: storeId, page: String(page) });
    if (search) params.set("search", search);
    if (status) params.set("status", status);
    if (selectedCategoryId) params.set("category_id", selectedCategoryId);
    else if (selectedLayer) params.set("layer", selectedLayer);
    window.history.replaceState(null, "", `/knowledge?${params}`);
    void load();
  }, [load, page, search, selectedCategoryId, selectedLayer, status, storeId]);

  useEffect(() => {
    if (!job || ["succeeded", "partially_succeeded", "failed"].includes(job.status)) return;
    const timer = window.setInterval(() => getImportJob(job.id).then(setJob).catch(() => setNotice(en ? "Import progress unavailable" : "导入进度暂时不可用")), 1500);
    return () => window.clearInterval(timer);
  }, [en, job]);

  async function addCategory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (categorySubmitting) return;
    const submittedForm = event.currentTarget;
    const form = new FormData(submittedForm);
    setCategorySubmitting(true);
    try {
      await createKnowledgeCategory({ store_id: storeId, parent_id: String(form.get("parent_id") || "") || null, name: String(form.get("name")), code: String(form.get("code")) });
      submittedForm.reset();
      setCategoryEditorOpen(false);
      setNotice(en ? "Category created" : "分类已创建");
      await load();
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : (en ? "Category creation failed" : "分类创建失败"));
    } finally {
      setCategorySubmitting(false);
    }
  }

  async function saveCategory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingCategory) return;
    const form = new FormData(event.currentTarget);
    try {
      await updateKnowledgeCategory(editingCategory.id, { name: String(form.get("name")), parent_id: String(form.get("parent_id") || "") || null });
      setEditingCategory(null);
      setCategoryEditorOpen(false);
      setNotice(en ? "Category updated" : "分类已更新");
      await load();
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : (en ? "Update failed" : "更新失败"));
    }
  }

  async function removeCategory(category: KnowledgeCategory) {
    if (!window.confirm(en ? "Delete this empty category?" : "删除这个空分类？")) return;
    try {
      await deleteKnowledgeCategory(category.id);
      if (selectedCategoryId === category.id) setSelectedCategoryId("");
      setNotice(en ? "Category deleted" : "分类已删除");
      await load();
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : (en ? "Delete failed" : "删除失败"));
    }
  }

  async function addEntry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (entrySubmitting) return;
    const submittedForm = event.currentTarget;
    const form = new FormData(submittedForm);
    setEntrySubmitting(true);
    try {
      await createKnowledgeEntry({ store_id: storeId, category_id: String(form.get("category_id") || "") || null, question: String(form.get("question")), answer: String(form.get("answer")), tags: String(form.get("tags") || "").split(",").map((tag) => tag.trim()).filter(Boolean), statement_type: String(form.get("statement_type")) as KnowledgeStatementType, customer_scope: String(form.get("customer_scope")) as KnowledgeCustomerScope });
      submittedForm.reset();
      setEntryEditorOpen(false);
      setNotice(en ? "FAQ draft created" : "FAQ 草稿已创建");
      await load();
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : (en ? "Create failed" : "创建失败"));
    } finally {
      setEntrySubmitting(false);
    }
  }

  async function saveEntry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingEntry) return;
    const form = new FormData(event.currentTarget);
    try {
      await updateKnowledgeEntry(editingEntry.id, { category_id: String(form.get("category_id") || "") || null, question: String(form.get("question")), answer: String(form.get("answer")), tags: String(form.get("tags") || "").split(",").map((tag) => tag.trim()).filter(Boolean), statement_type: String(form.get("statement_type")) as KnowledgeStatementType, customer_scope: String(form.get("customer_scope")) as KnowledgeCustomerScope });
      setEditingEntry(null);
      setEntryEditorOpen(false);
      setNotice(en ? "FAQ updated" : "FAQ 已更新");
      await load();
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : (en ? "Update failed" : "更新失败"));
    }
  }

  async function removeEntry(entry: KnowledgeEntry) {
    if (!window.confirm(en ? "Delete and archive this FAQ?" : "删除并归档这个 FAQ？")) return;
    try {
      await deleteKnowledgeEntry(entry.id);
      setNotice(en ? "FAQ deleted" : "FAQ 已删除");
      await load();
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : (en ? "Delete failed" : "删除失败"));
    }
  }

  async function publishEntry(entry: KnowledgeEntry) {
    if (entry.statement_type === "unknown") {
      setNotice(en ? "Choose a semantic type before approval" : "审批发布前必须选择知识语义类型");
      return;
    }
    const confirmed = window.confirm(en
      ? "Approve this exact version for internal AI review? FAQ content will not gain automatic reply permission."
      : "确认批准当前版本供 AI 内部复核使用？FAQ 不会因此获得自动回复权限。");
    if (!confirmed) return;
    try {
      await publishKnowledgeEntry(entry.id);
      setNotice(en ? "Version approved and queued for vectorization" : "当前版本已审批并进入向量化队列");
      await load();
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : (en ? "Approval failed" : "审批发布失败"));
    }
  }

  async function retryVectorization(entry: KnowledgeEntry) {
    if (entry.vectorization_status !== "failed" || retryingEntryId) return;
    setRetryingEntryId(entry.id);
    try {
      await retryKnowledgeVectorization(entry.id);
      setNotice(en ? "Vectorization retry queued" : "向量化重试已进入队列");
      await load();
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : (en ? "Retry failed" : "重试失败"));
    } finally {
      setRetryingEntryId(null);
    }
  }

  async function upload(file: File | undefined) {
    if (!file || !storeId) return;
    try {
      const accepted = await importKnowledge(storeId, file);
      setJob(await getImportJob(accepted.job_id));
      setNotice(en ? "File queued for import" : "文件已进入异步导入队列");
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : (en ? "Import failed" : "导入失败"));
    }
  }

  const categoryForm = <form key={editingCategory?.id ?? "new-category"} className="stack-form" onSubmit={editingCategory ? saveCategory : addCategory}>
    <label>{en ? "Category name" : "分类名称"}<input className="field" defaultValue={editingCategory?.name} name="name" required /></label>
    {!editingCategory ? <label>{en ? "Category code" : "分类编码"}<input className="field" name="code" pattern="[A-Za-z0-9_-]+" required /></label> : null}
    <label>{en ? "Parent category" : "父分类"}<select className="field" defaultValue={editingCategory?.parent_id ?? ""} name="parent_id"><option value="">{en ? "Root category" : "作为根分类"}</option>{categoryTree.filter((category) => !blockedParentIds.has(category.id)).map((category) => <option key={category.id} value={category.id}>{`${"— ".repeat(category.depth)}${category.name}`}</option>)}</select></label>
    <button className="primary-button" disabled={!storeId || categorySubmitting} type="submit">{categorySubmitting ? (en ? "Saving…" : "正在保存…") : editingCategory ? (en ? "Save category" : "保存分类") : (en ? "Add category" : "新增分类")}</button>
  </form>;

  const entryForm = <form key={editingEntry?.id ?? "new-entry"} className="stack-form" onSubmit={editingEntry ? saveEntry : addEntry}>
    <label>{en ? "Question" : "问题"}<input className="field" defaultValue={editingEntry?.question} maxLength={4000} name="question" required /></label>
    <label>{en ? "Answer" : "答案"}<textarea className="field min-h-32" defaultValue={editingEntry?.answer} maxLength={20000} name="answer" required /></label>
    <div className="form-row"><label>{en ? "Semantic type" : "知识语义类型"}<select className="field" defaultValue={editingEntry?.statement_type ?? "unknown"} name="statement_type" required>{statementTypes.map((item) => <option key={item.value} value={item.value}>{en ? item.en : item.zh}</option>)}</select></label><label>{en ? "Customer scope" : "客户范围"}<select className="field" defaultValue={editingEntry?.customer_scope ?? "none"} name="customer_scope" required>{customerScopes.map((item) => <option key={item.value} value={item.value}>{en ? item.en : item.zh}</option>)}</select></label></div>
    <p className="form-hint">{en ? "Publishing records your approval for this version. Customer-specific facts still require current real tool evidence." : "发布会记录你对当前版本的审批；客户实例事实仍必须取得当次真实工具证据。"}</p>
    <div className="form-row"><label>{en ? "Category" : "分类"}<select className="field" defaultValue={editingEntry?.category_id ?? selectedCategoryId} name="category_id"><option value="">{en ? "Uncategorized" : "未分类"}</option>{categoryTree.map((category) => <option key={category.id} value={category.id}>{`${"— ".repeat(category.depth)}${category.name}`}</option>)}</select></label><label>{en ? "Tags" : "标签（逗号分隔）"}<input className="field" defaultValue={editingEntry?.tags.join(", ")} name="tags" /></label></div>
    <button className="primary-button" disabled={!storeId || entrySubmitting} type="submit">{entrySubmitting ? (en ? "Saving…" : "正在保存…") : editingEntry ? (en ? "Save changes" : "保存修改") : (en ? "Create draft" : "创建草稿")}</button>
  </form>;

  return <AppShell><main className="management-page prototype-page">
    <section className="prototype-page-header"><div className="prototype-title"><span className="prototype-title-icon knowledge"><BookOpenText size={25} weight="duotone" /></span><div><h2>{en ? "Knowledge base" : "知识库"}<span>{en ? "FAQ · Products · Logistics policies" : "FAQ · 产品 · 物流政策"}</span></h2></div></div><div className="prototype-actions knowledge-header-actions"><label className="search-field header-search"><MagnifyingGlass size={17} /><input aria-label={en ? "Search question" : "搜索问题"} onChange={(event) => { setPage(1); setSearch(event.target.value); }} placeholder={en ? "Search FAQ" : "搜索 FAQ"} value={search} /></label><select aria-label={en ? "Status" : "发布状态"} className="compact-field toolbar-select" onChange={(event) => { setPage(1); setStatus(event.target.value); }} value={status}><option value="">{en ? "All status" : "全部状态"}</option><option value="draft">{en ? "Draft" : "草稿"}</option><option value="published">{en ? "Published" : "已发布"}</option><option value="archived">{en ? "Archived" : "已归档"}</option></select><select aria-label={en ? "Store" : "店铺"} className="compact-field header-select" onChange={(event) => { setPage(1); setSelectedCategoryId(""); setSelectedLayer(""); setStoreId(event.target.value); }} value={storeId}>{stores.map((id) => <option key={id} value={id}>{id.slice(0, 8)}</option>)}</select><label className="secondary-button file-button"><UploadSimple size={17} />{en ? "Bulk import" : "批量导入"}<input accept=".csv,.xlsx" className="sr-only" disabled={!storeId} onChange={(event) => void upload(event.target.files?.[0])} type="file" /></label><button className="primary-button" disabled={!storeId} onClick={() => { setEditingEntry(null); setEntryEditorOpen(true); }} type="button"><Plus size={18} weight="bold" />{en ? "New FAQ" : "新增知识"}</button></div></section>

    {notice ? <section aria-live="polite" className="inline-status" role="status"><span>{notice}</span></section> : null}
    {job ? <section className="inline-status" aria-live="polite"><strong>{en ? "Import" : "导入任务"}：{job.status}</strong><span>{job.succeeded_rows}/{job.total_rows} {en ? "succeeded" : "成功"}，{job.failed_rows} {en ? "failed" : "失败"}</span></section> : null}

    <div className="prototype-split knowledge-layout"><aside className="prototype-card knowledge-tree"><div className="panel-title"><span><Stack size={18} />{en ? "Knowledge layers" : "知识分层"}</span><button className="icon-action" disabled={!storeId} onClick={() => { setEditingCategory(null); setCategoryEditorOpen(true); }} aria-label={en ? "Manage categories" : "管理分类"} title={en ? "Manage categories" : "管理分类"} type="button"><Plus size={16} /></button></div><button aria-pressed={!selectedCategoryId && !selectedLayer} className={!selectedCategoryId && !selectedLayer ? "tree-item active" : "tree-item"} onClick={() => { setPage(1); setSelectedCategoryId(""); setSelectedLayer(""); }} type="button"><FolderOpen size={17} weight={!selectedCategoryId && !selectedLayer ? "fill" : "regular"} /><span>{en ? "All knowledge" : "全部知识"}</span>{!selectedCategoryId && !selectedLayer ? <small>{total}</small> : null}</button>{knowledgeLayers.map((layer) => <section className="tree-layer" key={layer.key}><button aria-pressed={selectedLayer === layer.key} className={selectedLayer === layer.key ? "tree-layer-title active" : "tree-layer-title"} onClick={() => { setPage(1); setSelectedCategoryId(""); setSelectedLayer(layer.key); }} type="button"><FolderSimple size={16} weight="fill" /><span>{en ? layer.en : layer.zh}</span>{selectedLayer === layer.key ? <small>{total}</small> : null}</button>{categoriesByLayer.get(layer.key)?.map((category) => <div className="tree-category-row" key={category.id} style={{ paddingInlineStart: 16 + Math.min(category.depth, 4) * 12 }}><button aria-pressed={selectedCategoryId === category.id} className={selectedCategoryId === category.id ? "tree-item active" : "tree-item"} onClick={() => { setPage(1); setSelectedLayer(""); setSelectedCategoryId(category.id); }} type="button"><FileText size={15} /><span>{category.name}</span></button><span className="tree-row-actions"><button aria-label={`${en ? "Edit" : "编辑"} ${category.name}`} onClick={() => { setEditingCategory(category); setCategoryEditorOpen(true); }} type="button"><PencilSimple size={14} /></button><button aria-label={`${en ? "Delete" : "删除"} ${category.name}`} onClick={() => void removeCategory(category)} type="button"><Trash size={14} /></button></span></div>)}</section>)}</aside>

      <section className="prototype-card knowledge-content"><header className="content-panel-heading"><div><p className="eyebrow">{en ? "FAQ CONTENT" : "FAQ 内容"}</p><h3>{selectedScopeLabel}</h3><small>{en ? "Embedding" : "向量模型"}：{vectorizationStatus?.model ?? "BAAI/bge-m3"}</small></div><span className="status-badge">{total} {en ? "items" : "条"}</span></header>{vectorizationStatus ? <dl className="vector-mini-grid"><div><dt>{en ? "Pending" : "待处理"}</dt><dd>{vectorizationStatus.counts.pending}</dd></div><div><dt>{en ? "Processing" : "处理中"}</dt><dd>{vectorizationStatus.counts.processing}</dd></div><div><dt>{en ? "Ready" : "已就绪"}</dt><dd>{vectorizationStatus.counts.ready}</dd></div><div><dt>{en ? "Failed" : "失败"}</dt><dd>{vectorizationStatus.counts.failed}</dd></div></dl> : null}{loading ? <LoadingState /> : error ? <ErrorState message={error} retry={() => void load()} /> : !storeId ? <div className="state-box" role="status"><p>{en ? "Create a store to manage knowledge." : "请先创建店铺，再管理知识。"}</p><Link className="secondary-button mt-3" href="/settings/stores">{en ? "Create store" : "创建店铺"}</Link></div> : !entries.length ? <EmptyState label={en ? `No knowledge in ${selectedScopeLabel}` : `${selectedScopeLabel}暂无知识，可新增知识或批量导入`} /> : <div className="knowledge-entry-list">{entries.map((entry) => <article className="knowledge-entry" key={entry.id}><header><div><span className="entry-document"><FileText size={18} weight="duotone" /></span><strong>{entry.question}</strong></div><div className="entry-actions"><button onClick={() => { setEditingEntry(entry); setEntryEditorOpen(true); }} type="button"><PencilSimple size={15} />{en ? "Edit" : "编辑"}</button><button onClick={() => void removeEntry(entry)} type="button"><Trash size={15} />{en ? "Delete" : "删除"}</button></div></header><div className="answer-panel"><Lightbulb size={18} weight="fill" /><p>{entry.answer}</p></div><div className="entry-meta"><span>{statusText(entry.status, en)}</span><span>{statusText(entry.vectorization_status, en)}</span><span>{statementTypes.find((item) => item.value === entry.statement_type)?.[en ? "en" : "zh"]}</span><span>{customerScopes.find((item) => item.value === entry.customer_scope)?.[en ? "en" : "zh"]}</span><span>{entry.publication_approval === "draft" ? (en ? "Not approved" : "未审批") : (en ? "Approved for internal review" : "已批准供内部复核")}</span><span>{en ? "Used" : "使用"} {entry.usage_count} {en ? "times" : "次"}</span>{entry.satisfaction_rate != null ? <span>{en ? "Satisfaction" : "满意度"} {(entry.satisfaction_rate * 100).toFixed(0)}%</span> : null}</div><footer><div className="entry-tags">{entry.tags.map((tag) => <span key={tag}>#{tag}</span>)}</div><div className="entry-lifecycle">{entry.status !== "published" ? <button disabled={entry.statement_type === "unknown"} onClick={() => void publishEntry(entry)} type="button"><CheckCircle size={15} />{en ? "Approve & publish" : "审批并发布"}</button> : null}{entry.status !== "archived" ? <button onClick={() => void archiveKnowledgeEntry(entry.id).then(load).catch((caught) => setNotice(caught instanceof Error ? caught.message : (en ? "Archive failed" : "归档失败")))} type="button"><Archive size={15} />{en ? "Archive" : "归档"}</button> : null}{entry.vectorization_status === "failed" ? <button disabled={!vectorizationStatus?.worker_enabled || retryingEntryId === entry.id} onClick={() => void retryVectorization(entry)} type="button"><ArrowClockwise size={15} />{retryingEntryId === entry.id ? (en ? "Queuing…" : "正在入队…") : (en ? "Retry vector" : "重试向量化")}</button> : null}</div></footer></article>)}</div>}<div className="pagination-row"><small>{en ? `Page ${page}` : `第 ${page} 页`}</small><div><button className="secondary-button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)} type="button">{en ? "Previous" : "上一页"}</button><button className="secondary-button" disabled={page * 20 >= total} onClick={() => setPage((value) => value + 1)} type="button">{en ? "Next" : "下一页"}</button></div></div></section>
    </div>

    {categoryEditorOpen ? <EditorModal title={editingCategory ? (en ? "Edit category" : "编辑分类") : (en ? "New category" : "新增分类")} onClose={() => { setCategoryEditorOpen(false); setEditingCategory(null); }}>{categoryForm}</EditorModal> : null}
    {entryEditorOpen ? <EditorModal title={editingEntry ? (en ? "Edit FAQ" : "编辑 FAQ") : (en ? "New FAQ" : "新增知识")} onClose={() => { setEntryEditorOpen(false); setEditingEntry(null); }}>{entryForm}</EditorModal> : null}
  </main></AppShell>;
}

function EditorModal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return <div className="editor-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) onClose(); }}><section aria-modal="true" className="editor-modal" role="dialog" aria-label={title}><header><h3>{title}</h3><button aria-label="关闭" onClick={onClose} type="button"><X size={20} /></button></header>{children}</section></div>;
}
