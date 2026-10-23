"use client";

import Link from "next/link";
import "./knowledge-prototype.css";
import {
  Folder,
  Trash,
  Truck,
} from "@phosphor-icons/react";
import { FormEvent, Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  listStores,
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
  type StoreView,
} from "../../lib/api";
import { useLanguage } from "../../lib/i18n";

type CategoryTreeItem = KnowledgeCategory & { depth: number };
type PresetCategoryKey = "goods" | "logistics" | "payment" | "aftersales" | "customs";
type PresetCategory = { key: PresetCategoryKey; name: string; group: "核心业务线" | "合规与政策"; description: string; icon: "folder" | "truck" };
type KnowledgeParameters = { chunk: number; overlap: number; model: string; topK: number; score: number; rerank: boolean; rerankModel: "BAAI/bge-reranker-large" };
type DemoDocument = { id: string; storeId: string; categoryId: string | null; file: File; createdAt: string; vectorizationStatus: "pending" | "disabled" };
type KnowledgeRow = { id: string; categoryId: string | null; title: string; type: "pdf" | "xlsx" | "txt"; updated: string; version: number; vector: string; review: "approved" | "pending" | "draft"; entry?: KnowledgeEntry; demo?: DemoDocument };

const defaultParameters: KnowledgeParameters = { chunk: 500, overlap: 50, model: "BAAI/bge-m3", topK: 20, score: 0.52, rerank: true, rerankModel: "BAAI/bge-reranker-large" };
const presetCategories: PresetCategory[] = [
  { key: "goods", name: "商品与目录", group: "核心业务线", icon: "folder", description: "商品资料、目录与常见说明。" },
  { key: "logistics", name: "物流与仓储", group: "核心业务线", icon: "truck", description: "包含物流时效、运费规则、仓储管理、发货与配送等相关知识，供客服参考使用。" },
  { key: "payment", name: "支付与结算", group: "核心业务线", icon: "folder", description: "支付与结算业务相关知识。" },
  { key: "aftersales", name: "售后与退换", group: "核心业务线", icon: "folder", description: "售后、退款及退换货相关知识。" },
  { key: "customs", name: "关务与合规", group: "合规与政策", icon: "folder", description: "关务与合规政策相关知识。" },
];
const presetGroups: PresetCategory["group"][] = ["核心业务线", "合规与政策"];

function knowledgeFileType(name: string | null): KnowledgeRow["type"] {
  const extension = name?.split(".").pop()?.toLowerCase();
  if (extension === "pdf") return "pdf";
  if (extension === "xlsx" || extension === "xls") return "xlsx";
  return "txt";
}

function knowledgeDate(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf()) ? "—" : parsed.toLocaleString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false });
}

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

export default function KnowledgePage() {
  const en = useLanguage() === "en";
  const [storeId, setStoreId] = useState("");
  const [stores, setStores] = useState<string[]>([]);
  const [storeDetails, setStoreDetails] = useState<StoreView[]>([]);
  const [categories, setCategories] = useState<KnowledgeCategory[]>([]);
  const [entries, setEntries] = useState<KnowledgeEntry[]>([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState("");
  const [selectedEmptyPreset, setSelectedEmptyPreset] = useState<PresetCategoryKey | "">("");
  const [categoryCounts, setCategoryCounts] = useState<Record<string, number | null>>({});
  const [allCategoryCount, setAllCategoryCount] = useState<number | null>(null);
  const [countRevision, setCountRevision] = useState(0);
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
  const [detailRow, setDetailRow] = useState<KnowledgeRow | null>(null);
  const [parametersOpen, setParametersOpen] = useState(false);
  const [parameters, setParameters] = useState<KnowledgeParameters>(defaultParameters);
  const [parameterDraft, setParameterDraft] = useState<KnowledgeParameters>(defaultParameters);
  const [fileTypeFilter, setFileTypeFilter] = useState("");
  const [vectorFilter, setVectorFilter] = useState("");
  const [reviewFilter, setReviewFilter] = useState("");
  const [addMode, setAddMode] = useState<"upload" | "manual">("upload");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedUploadCategoryId, setSelectedUploadCategoryId] = useState("");
  const [segmentMode, setSegmentMode] = useState("semantic");
  const [parserMode, setParserMode] = useState<"standard" | "deep">("standard");
  const [vectorizeAfterUpload, setVectorizeAfterUpload] = useState(true);
  const [demoDocuments, setDemoDocuments] = useState<DemoDocument[]>([]);
  const [categoryEditorOpen, setCategoryEditorOpen] = useState(false);
  const [entryEditorOpen, setEntryEditorOpen] = useState(false);
  const [categorySubmitting, setCategorySubmitting] = useState(false);
  const [deletingCategoryId, setDeletingCategoryId] = useState<string | null>(null);
  const [pendingCategoryDelete, setPendingCategoryDelete] = useState<KnowledgeCategory | null>(null);
  const [categoryReloadRevision, setCategoryReloadRevision] = useState(0);
  const [entrySubmitting, setEntrySubmitting] = useState(false);
  const loadRequestId = useRef(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const categoryTree = useMemo(() => flattenCategoryTree(categories.filter((category) => category.store_id === storeId)), [categories, storeId]);
  // 原型的五个业务分类是展示模板；只有当前店铺已有同名服务端分类时才绑定真实 ID。
  const presetBindings = useMemo(() => {
    const bindings = new Map<PresetCategoryKey, CategoryTreeItem>();
    const used = new Set<string>();
    for (const preset of presetCategories) {
      const matches = categoryTree.filter((category) => category.depth === 0 && !used.has(category.id) && category.name.trim() === preset.name);
      const match = matches.find((category) => category.code.toLowerCase() === preset.key) ?? matches[0];
      if (match) { bindings.set(preset.key, match); used.add(match.id); }
    }
    return bindings;
  }, [categoryTree]);
  const customCategories = useMemo(() => {
    const presetIds = new Set([...presetBindings.values()].map((category) => category.id));
    return categoryTree.filter((category) => !presetIds.has(category.id));
  }, [categoryTree, presetBindings]);
  const selectedPreset = presetCategories.find((preset) => selectedEmptyPreset === preset.key || presetBindings.get(preset.key)?.id === selectedCategoryId) ?? null;
  const effectiveCategoryId = selectedCategoryId || (selectedEmptyPreset ? presetBindings.get(selectedEmptyPreset)?.id ?? "" : "");
  const isEmptyPreset = Boolean(selectedEmptyPreset && !effectiveCategoryId);
  const selectedCategory = categoryTree.find((category) => category.id === effectiveCategoryId) ?? null;
  const selectedScopeLabel = selectedPreset?.name ?? selectedCategory?.name ?? (en ? "All knowledge" : "全部知识");
  const categoryIdSignature = categoryTree.map((category) => category.id).sort().join("|");
  const blockedParentIds = useMemo(() => editingCategory ? collectDescendantIds(categories, editingCategory.id) : new Set<string>(), [categories, editingCategory]);
  const configuredModel = vectorizationStatus?.model ?? defaultParameters.model;
  const storeName = storeDetails.find((store) => store.id === storeId)?.name ?? storeId.slice(0, 8);
  const rows = useMemo<KnowledgeRow[]>(() => {
    const realRows = entries.filter((entry) => !isEmptyPreset && entry.store_id === storeId && (!effectiveCategoryId || entry.category_id === effectiveCategoryId)).map((entry): KnowledgeRow => ({
      id: entry.id,
      categoryId: entry.category_id,
      title: entry.question,
      type: knowledgeFileType(entry.source),
      updated: entry.updated_at,
      version: entry.document_version,
      vector: entry.vectorization_status,
      review: entry.publication_approval !== "draft" ? "approved" : entry.status === "draft" ? "pending" : "draft",
      entry,
    }));
    const localRows = demoDocuments.filter((document) => !isEmptyPreset && document.storeId === storeId && (!effectiveCategoryId || document.categoryId === effectiveCategoryId)).map((document): KnowledgeRow => ({
      id: document.id,
      categoryId: document.categoryId,
      title: document.file.name,
      type: knowledgeFileType(document.file.name),
      updated: document.createdAt,
      version: 1,
      vector: document.vectorizationStatus,
      review: "pending",
      demo: document,
    }));
    return [...localRows, ...realRows].filter((row) => {
      if (row.demo && search && !row.title.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())) return false;
      return (!fileTypeFilter || row.type === fileTypeFilter) && (!vectorFilter || row.vector === vectorFilter) && (!reviewFilter || row.review === reviewFilter);
    });
  }, [demoDocuments, effectiveCategoryId, entries, fileTypeFilter, isEmptyPreset, reviewFilter, search, storeId, vectorFilter]);

  const load = useCallback(async () => {
    if (!storeId) return;
    const requestId = ++loadRequestId.current;
    setLoading(true);
    setError("");
    try {
      const query = new URLSearchParams({ page: String(page), page_size: "20", store_id: storeId });
      if (search) query.set("search", search);
      if (status) query.set("status", status);
      if (effectiveCategoryId) query.set("category_id", effectiveCategoryId);
      const [categoryData, entryData, vectorData] = await Promise.all([
        listKnowledgeCategories(storeId),
        isEmptyPreset ? Promise.resolve({ items: [] as KnowledgeEntry[], page, page_size: 20, total: 0 }) : listKnowledgeEntries(query),
        getKnowledgeVectorizationStatus(storeId),
      ]);
      // 快速切换分类时，只允许最后一次请求更新列表，避免旧响应覆盖当前选择。
      if (requestId !== loadRequestId.current) return;
      setCategories(categoryData);
      // URL 可能保留其他店铺的分类；按当前店铺的真实分类重新校验，避免显示空列表和错误高亮。
      if (selectedCategoryId && !categoryData.some((category) => category.id === selectedCategoryId && category.store_id === storeId)) {
        setSelectedCategoryId("");
        setPage(1);
      }
      setEntries(entryData.items);
      setTotal(entryData.total);
      setVectorizationStatus(vectorData);
      setParameters((current) => current.model === vectorData.model ? current : { ...current, model: vectorData.model });
    } catch (caught) {
      if (requestId !== loadRequestId.current) return;
      setError(caught instanceof Error ? caught.message : (en ? "Knowledge loading failed" : "知识库加载失败"));
    } finally {
      if (requestId === loadRequestId.current) setLoading(false);
    }
  }, [effectiveCategoryId, en, isEmptyPreset, page, search, selectedCategoryId, status, storeId]);

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
      const presetKey = params.get("category_preset");
      const validPresetKey = !categoryId && presetCategories.some((preset) => preset.key === presetKey) ? presetKey as PresetCategoryKey : "";
      setSelectedEmptyPreset(validPresetKey);
      setPage(Number(params.get("page") || 1));
    }).catch((caught: unknown) => {
      if (!isAuthenticationError(caught)) {
        setError(caught instanceof Error ? caught.message : (en ? "User loading failed" : "用户信息加载失败"));
        setLoading(false);
      }
    });
    void listStores().then(setStoreDetails).catch((caught: unknown) => {
      setNotice(caught instanceof Error ? caught.message : (en ? "Store names unavailable" : "暂时无法加载店铺名称"));
    });
  }, [en]);

  useEffect(() => () => { loadRequestId.current += 1; }, []);

  useEffect(() => {
    if (!storeId) return;
    const params = new URLSearchParams({ store_id: storeId, page: String(page) });
    if (search) params.set("search", search);
    if (status) params.set("status", status);
    if (selectedCategoryId) params.set("category_id", selectedCategoryId);
    else if (selectedEmptyPreset) params.set("category_preset", selectedEmptyPreset);
    window.history.replaceState(null, "", `/knowledge?${params}`);
    void load();
  }, [categoryReloadRevision, load, page, search, selectedCategoryId, selectedEmptyPreset, status, storeId]);

  useEffect(() => {
    let active = true;
    const ids = categoryIdSignature ? categoryIdSignature.split("|") : [];
    setCategoryCounts({});
    setAllCategoryCount(null);
    if (!storeId) return () => { active = false; };
    // 列表总数受当前搜索和筛选影响；角标单独查询当前店铺各分类的完整总数。
    void (async () => {
      const targets = ["", ...ids];
      for (let offset = 0; offset < targets.length; offset += 4) {
        const batch = targets.slice(offset, offset + 4);
        const results = await Promise.all(batch.map(async (id) => {
          const query = new URLSearchParams({ page: "1", page_size: "1", store_id: storeId });
          if (id) query.set("category_id", id);
          try { return { id, total: (await listKnowledgeEntries(query)).total }; }
          catch { return { id, total: null }; }
        }));
        if (!active) return;
        for (const result of results) {
          if (result.id) setCategoryCounts((current) => ({ ...current, [result.id]: result.total }));
          else setAllCategoryCount(result.total);
        }
      }
    })();
    return () => { active = false; };
  }, [categoryIdSignature, countRevision, storeId]);

  useEffect(() => {
    if (!job || ["succeeded", "partially_succeeded", "failed"].includes(job.status)) return;
    const timer = window.setInterval(() => getImportJob(job.id).then((next) => {
      setJob(next);
      if (["succeeded", "partially_succeeded", "failed"].includes(next.status)) {
        if (next.status !== "failed") setCountRevision((value) => value + 1);
        void load();
      }
    }).catch(() => setNotice(en ? "Import progress unavailable" : "导入进度暂时不可用")), 1500);
    return () => window.clearInterval(timer);
  }, [en, job, load]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || deletingCategoryId) return;
      setParametersOpen(false);
      setDetailRow(null);
      setCategoryEditorOpen(false);
      setEntryEditorOpen(false);
      setPendingCategoryDelete(null);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [deletingCategoryId]);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(""), 5000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  async function addCategory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (categorySubmitting) return;
    const submittedForm = event.currentTarget;
    const form = new FormData(submittedForm);
    const name = String(form.get("name") ?? "").trim();
    if (!name) { setNotice("请输入分类名称"); return; }
    if (categoryTree.some((category) => category.name.trim().toLocaleLowerCase() === name.toLocaleLowerCase())) {
      setNotice("当前店铺已有同名分类");
      return;
    }
    const preset = presetCategories.find((item) => item.name === name);
    setCategorySubmitting(true);
    try {
      const created = await createKnowledgeCategory({ store_id: storeId, parent_id: null, name, code: preset?.key ?? `category_${crypto.randomUUID().slice(0, 8)}` });
      submittedForm.reset();
      setCategoryEditorOpen(false);
      setCategories((current) => [...current, created]);
      setSelectedEmptyPreset("");
      setSelectedCategoryId(created.id);
      setPage(1);
      setNotice(en ? "Category created" : "分类已创建");
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

  function requestCategoryDelete(category: KnowledgeCategory) {
    if (deletingCategoryId || category.store_id !== storeId || !customCategories.some((item) => item.id === category.id)) return;
    if (demoDocuments.some((document) => document.storeId === storeId && document.categoryId === category.id)) {
      setNotice(en ? "Clear this category's page demo files by refreshing before deleting it" : "该分类含页面演示文件，请刷新页面清空后再删除");
      return;
    }
    setCategoryEditorOpen(false);
    setPendingCategoryDelete(category);
  }

  async function removeCategory() {
    const category = pendingCategoryDelete;
    if (!category || deletingCategoryId) return;
    if (category.store_id !== storeId || !customCategories.some((item) => item.id === category.id)) {
      setPendingCategoryDelete(null);
      return;
    }
    if (demoDocuments.some((document) => document.storeId === storeId && document.categoryId === category.id)) {
      setNotice(en ? "Clear this category's page demo files by refreshing before deleting it" : "该分类含页面演示文件，请刷新页面清空后再删除");
      setPendingCategoryDelete(null);
      return;
    }
    setDeletingCategoryId(category.id);
    try {
      await deleteKnowledgeCategory(category.id);
      setPendingCategoryDelete(null);
      setCategories((current) => current.filter((item) => item.id !== category.id));
      if (editingCategory?.id === category.id) setEditingCategory(null);
      setSelectedCategoryId((current) => current === category.id ? "" : current);
      setPage(1);
      setCategoryReloadRevision((current) => current + 1);
      setNotice(en ? "Category deleted" : "分类已删除");
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : (en ? "Delete failed" : "删除失败"));
    } finally {
      setDeletingCategoryId(null);
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
      setCountRevision((value) => value + 1);
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
      setCountRevision((value) => value + 1);
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
      setCountRevision((value) => value + 1);
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : (en ? "Delete failed" : "删除失败"));
    }
  }

  async function archiveEntry(entry: KnowledgeEntry) {
    if (!window.confirm("归档当前知识？归档后不再用于检索建议。")) return;
    try {
      await archiveKnowledgeEntry(entry.id);
      setNotice("知识已归档");
      await load();
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : "归档失败");
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

  async function upload(file: File | undefined): Promise<boolean> {
    if (!file || !storeId) return false;
    try {
      const accepted = await importKnowledge(storeId, file);
      setJob(await getImportJob(accepted.job_id));
      setNotice(en ? "File queued for import" : "文件已进入异步导入队列");
      return true;
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : (en ? "Import failed" : "导入失败"));
      return false;
    }
  }

  function chooseFile(file: File | undefined) {
    if (!file) return;
    const extension = file.name.split(".").pop()?.toLowerCase();
    if (!extension || !["csv", "xlsx", "pdf", "doc", "docx", "md", "xls", "txt"].includes(extension)) {
      setNotice("请选择支持的文件格式");
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      setNotice("单个文件不能超过 50 MB");
      return;
    }
    setSelectedFile(file);
  }

  async function submitSelectedFile() {
    if (!selectedFile || !storeId) {
      setNotice("请先选择知识文件");
      return;
    }
    const extension = selectedFile.name.split(".").pop()?.toLowerCase();
    if (extension === "csv" || extension === "xlsx") {
      if (!await upload(selectedFile)) return;
      setNotice("CSV/XLSX 已提交真实导入；分类以文件中的 category_code 为准");
    } else {
      setDemoDocuments((current) => [{ id: crypto.randomUUID(), storeId, categoryId: selectedUploadCategoryId || null, file: selectedFile, createdAt: new Date().toISOString(), vectorizationStatus: vectorizeAfterUpload ? "pending" : "disabled" }, ...current]);
      setNotice("文件已加入本页演示列表，刷新后清空；未上传到服务端");
    }
    setEntryEditorOpen(false);
    setSelectedFile(null);
    setSearch("");
    setFileTypeFilter("");
    setVectorFilter("");
    setReviewFilter("");
    setPage(1);
  }

  function openAdd() {
    if (isEmptyPreset && selectedPreset) {
      setEditingCategory(null);
      setCategoryEditorOpen(true);
      setNotice(`请先将“${selectedPreset.name}”保存到当前店铺，再添加知识`);
      return;
    }
    setEditingEntry(null);
    setSelectedFile(null);
    setSelectedUploadCategoryId(selectedCategoryId);
    setSegmentMode("semantic");
    setParserMode("standard");
    setVectorizeAfterUpload(true);
    setAddMode("upload");
    setEntryEditorOpen(true);
  }

  function saveParameters() {
    if (!Number.isInteger(parameterDraft.chunk) || parameterDraft.chunk < 1 || parameterDraft.chunk > 10000 || !Number.isInteger(parameterDraft.overlap) || parameterDraft.overlap < 0 || parameterDraft.overlap >= parameterDraft.chunk) {
      setNotice("请检查分块大小与重叠大小");
      return;
    }
    setParameters(parameterDraft);
    setParametersOpen(false);
    setNotice("参数已保存到本页演示状态；项目实际检索配置未修改");
  }

  const categoryForm = <form className="kb-modal-form" key={editingCategory?.id ?? "new-category"} onSubmit={editingCategory ? saveCategory : addCategory}>
    <div className="modal-content">
      <label className="label" htmlFor="newCategoryName">分类名称</label>
      <input className="field" defaultValue={editingCategory?.name ?? (isEmptyPreset ? selectedPreset?.name : "")} id="newCategoryName" maxLength={30} name="name" placeholder="例如：品牌服务政策" required />
      {editingCategory ? <label className="label kb-extra-field">父分类<select className="field" defaultValue={editingCategory.parent_id ?? ""} name="parent_id"><option value="">作为根分类</option>{categoryTree.filter((category) => !blockedParentIds.has(category.id)).map((category) => <option key={category.id} value={category.id}>{`${"— ".repeat(category.depth)}${category.name}`}</option>)}</select></label> : <input defaultValue="" name="parent_id" type="hidden" />}
      <p className="parameter-hint">{editingCategory ? "分类保存到当前店铺，并按服务端权限与店铺范围校验。" : isEmptyPreset ? "保存同名预置分类后，即可在当前店铺归属知识。" : "分类只添加到当前店铺，归入“自定义分类”。保存后会保留在当前店铺。"}</p>
    </div>
    <div className="modal-foot"><button className="btn" onClick={() => setCategoryEditorOpen(false)} type="button">取消</button><button className="btn primary" disabled={!storeId || categorySubmitting} type="submit">{categorySubmitting ? "正在保存…" : editingCategory ? "保存分类" : "添加分类"}</button></div>
  </form>;

  const entryForm = <form className="kb-modal-form" key={editingEntry?.id ?? "new-entry"} onSubmit={editingEntry ? saveEntry : addEntry}>
    <div className="modal-content kb-edit-fields">
      <label className="label">知识标题<input className="field" defaultValue={editingEntry?.question} maxLength={4000} name="question" required /></label>
      <label className="label">知识内容<textarea className="field" defaultValue={editingEntry?.answer} maxLength={20000} name="answer" required rows={7} /></label>
      <div className="form-row"><label className="label">知识语义类型<select className="field" defaultValue={editingEntry?.statement_type ?? "unknown"} name="statement_type" required>{statementTypes.map((item) => <option key={item.value} value={item.value}>{en ? item.en : item.zh}</option>)}</select></label><label className="label">客户范围<select className="field" defaultValue={editingEntry?.customer_scope ?? "none"} name="customer_scope" required>{customerScopes.map((item) => <option key={item.value} value={item.value}>{en ? item.en : item.zh}</option>)}</select></label></div>
      <div className="form-row"><label className="label">归属分类<select className="field" defaultValue={editingEntry?.category_id ?? selectedCategoryId} name="category_id"><option value="">未分类</option>{categoryTree.map((category) => <option key={category.id} value={category.id}>{`${"— ".repeat(category.depth)}${category.name}`}</option>)}</select></label><label className="label">标签（逗号分隔）<input className="field" defaultValue={editingEntry?.tags.join(", ")} name="tags" /></label></div>
      <p className="parameter-hint">内容或语义范围修改后会生成新版本，并撤销原审批。</p>
    </div>
    <div className="modal-foot"><button className="btn" onClick={() => setEntryEditorOpen(false)} type="button">取消</button><button className="btn primary" disabled={!storeId || entrySubmitting} type="submit">{entrySubmitting ? "正在保存…" : editingEntry ? "保存修改" : "保存知识"}</button></div>
  </form>;

  const closeDialogs = () => { if (deletingCategoryId) return; setParametersOpen(false); setDetailRow(null); setCategoryEditorOpen(false); setEntryEditorOpen(false); setPendingCategoryDelete(null); };
  const anyDialogOpen = parametersOpen || Boolean(detailRow) || categoryEditorOpen || entryEditorOpen || Boolean(pendingCategoryDelete);
  const localCount = demoDocuments.filter((document) => !isEmptyPreset && document.storeId === storeId && (!effectiveCategoryId || document.categoryId === effectiveCategoryId)).length;
  const scopeDescription = selectedPreset?.description ?? (selectedCategory ? "当前店铺新增的自定义知识分类。" : "查看当前店铺的全部知识文档，供客服参考使用。");
  const scopeServerCount = isEmptyPreset ? 0 : effectiveCategoryId ? categoryCounts[effectiveCategoryId] ?? total : allCategoryCount ?? total;
  const categoryCountLabel = (categoryId: string | undefined): string => {
    if (!categoryId) return "0";
    const count = categoryCounts[categoryId];
    if (count === undefined) return "…";
    if (count === null) return "—";
    return String(count + demoDocuments.filter((document) => document.storeId === storeId && document.categoryId === categoryId).length);
  };
  const detailCategory = detailRow ? categories.find((category) => category.id === detailRow.categoryId)?.name ?? "未分类" : "";
  const detailApproval = detailRow?.review === "approved" ? "已通过" : detailRow?.review === "pending" ? "待审批" : "草稿";
  const detailSemantic = detailRow?.entry ? statementTypes.find((item) => item.value === detailRow.entry?.statement_type)?.[en ? "en" : "zh"] ?? "未分类" : "知识文档 · 页面演示";

  return <AppShell><div className="knowledge-page">
    <input accept=".csv,.xlsx,.pdf,.doc,.docx,.md,.xls,.txt" aria-label="选择知识文件" disabled={!storeId} hidden onChange={(event) => chooseFile(event.target.files?.[0])} ref={fileInputRef} type="file" />
    <header className="topbar">
      <div className="title"><span className="title-icon" aria-hidden="true">▣</span><div><h1>知识库</h1><p>管理客服建议使用的内部知识</p></div></div>
      <div className="top-actions">
        <label className="store">▣ 当前店铺：<select aria-label="当前店铺" disabled={!stores.length || categorySubmitting || Boolean(deletingCategoryId)} onChange={(event) => { setStoreId(event.target.value); setSelectedCategoryId(""); setSelectedEmptyPreset(""); setPendingCategoryDelete(null); setSearch(""); setFileTypeFilter(""); setVectorFilter(""); setReviewFilter(""); setPage(1); }} value={storeId}>{stores.map((id) => <option key={id} value={id}>{storeDetails.find((store) => store.id === id)?.name ?? id.slice(0, 8)}</option>)}</select></label>
        <button className="btn" onClick={() => { setParameterDraft({ ...parameters }); setParametersOpen(true); }} type="button">☷　流程参数</button>
        <button aria-label="新增知识" className="btn primary" disabled={!storeId} onClick={openAdd} type="button">＋　新增知识</button>
      </div>
    </header>
    <div className="workspace">
      <aside className="categories" aria-label="知识分类"><div className="category-head"><h2>知识分类</h2><button aria-label="管理分类" className="icon-btn" disabled={!storeId} onClick={() => { setEditingCategory(null); setCategoryEditorOpen(true); }} title="新增分类" type="button">＋</button></div>
        <button aria-current={!selectedCategoryId && !selectedEmptyPreset} className={`cat${!selectedCategoryId && !selectedEmptyPreset ? " active" : ""}`} onClick={() => { setSelectedCategoryId(""); setSelectedEmptyPreset(""); setPage(1); }} type="button"><Folder size={18} weight="fill" /><span>全部知识</span></button>
        {presetGroups.map((group) => <Fragment key={group}><div className="group-label">{group}</div>{presetCategories.filter((preset) => preset.group === group).map((preset) => {
          const category = presetBindings.get(preset.key);
          const active = selectedEmptyPreset === preset.key || Boolean(category && selectedCategoryId === category.id);
          return <button aria-current={active} aria-label={preset.name} className={`cat${active ? " active" : ""}`} key={preset.key} onClick={() => { setSelectedCategoryId(category?.id ?? ""); setSelectedEmptyPreset(category ? "" : preset.key); setPage(1); }} type="button">{preset.icon === "truck" ? <Truck size={18} /> : <Folder size={18} weight="fill" />}<span className="kb-category-name">{preset.name}</span><span className="count">{categoryCountLabel(category?.id)}</span></button>;
        })}</Fragment>)}
        {customCategories.length ? <><div className="group-label">自定义分类</div>{customCategories.map((category) => <div className="kb-custom-category-row" key={category.id}><button aria-current={selectedCategoryId === category.id} aria-label={category.name} className={`cat${selectedCategoryId === category.id ? " active" : ""}`} onClick={() => { setSelectedCategoryId(category.id); setSelectedEmptyPreset(""); setPage(1); }} style={{ paddingInlineStart: 10 + Math.min(category.depth, 3) * 14 }} type="button"><Folder size={18} weight="fill" /><span className="kb-category-name">{category.name}</span><span className="count">{categoryCountLabel(category.id)}</span></button><button aria-label={`删除分类：${category.name}`} className="kb-custom-category-delete" disabled={Boolean(deletingCategoryId)} onClick={() => requestCategoryDelete(category)} title={`删除分类：${category.name}`} type="button"><Trash size={16} /></button></div>)}</> : null}
      </aside>
      <main className="main">
        <section className="scope"><div className="scope-copy"><span className="scope-icon" aria-hidden="true">▣</span><div><h2>{selectedScopeLabel}</h2><p>{scopeDescription}</p></div></div><span className="total">{scopeServerCount + localCount} 篇知识</span></section>
        <div className="safety">ⓘ　仅供内部客服辅助使用 · 坐席确认后发送</div>
        <div className="config-summary">分块：{parameters.chunk}　·　重叠：{parameters.overlap}　·　召回：{parameters.topK}　·　阈值：{parameters.score.toFixed(2)}　·　模型：{parameters.model}{parameters !== defaultParameters ? " · 本页演示" : ""}</div>
        <div className="toolbar"><label className="search"><span aria-hidden="true">⌕</span><input aria-label="搜索知识" className="field" maxLength={200} onChange={(event) => { setPage(1); setSearch(event.target.value); }} placeholder="搜索知识名称或关键词" value={search} /></label>
          <select aria-label="文件类型" className="field filter" onChange={(event) => setFileTypeFilter(event.target.value)} value={fileTypeFilter}><option value="">全部类型</option><option value="pdf">PDF</option><option value="xlsx">Excel</option><option value="txt">文本知识</option></select>
          <select aria-label="向量状态" className="field filter" onChange={(event) => setVectorFilter(event.target.value)} value={vectorFilter}><option value="">向量状态</option><option value="ready">已就绪</option><option value="pending">待处理</option><option value="disabled">未启用</option><option value="failed">失败</option></select>
          <select aria-label="内部审批状态" className="field filter" onChange={(event) => setReviewFilter(event.target.value)} value={reviewFilter}><option value="">审批状态</option><option value="approved">已通过</option><option value="pending">待审批</option><option value="draft">草稿</option></select>
        </div>
        <section aria-label="知识文档列表" className="table"><div className="table-head"><span>文件名称</span><span>更新时间</span><span>向量状态</span><span>内部审批状态</span><span>操作</span></div>
          {loading ? <div className="empty"><LoadingState /></div> : error ? <div className="empty"><ErrorState message={error} retry={() => void load()} /></div> : !storeId ? <div className="empty" role="status">请先创建店铺，再管理知识。<br /><Link className="btn" href="/settings/stores">创建店铺</Link></div> : !rows.length ? <div className="empty"><EmptyState label="当前条件下没有知识文档" /></div> : rows.map((row) => <div className="row" key={row.id}><div className="file"><span className={`file-icon ${row.type}`}>{row.type === "pdf" ? "PDF" : row.type === "xlsx" ? "X" : "TXT"}</span><div className="kb-file-copy"><strong title={row.title}>{row.title}</strong><small>{row.demo ? <span className="demo-label">页面演示 · 刷新后清空</span> : `v${row.version} · ${row.entry?.source ?? "内部知识"}`}</small></div></div><span className="kb-updated">{knowledgeDate(row.updated)}</span><span className="state"><i className={`dot${row.vector === "ready" ? "" : " wait"}`} />{row.vector === "ready" ? "已就绪" : row.vector === "pending" || row.vector === "processing" ? "待处理" : row.vector === "failed" ? "失败" : "未启用"}</span><span><span className={`badge ${row.review === "approved" ? "ok" : row.review === "pending" ? "wait" : "draft"}`}>{row.review === "approved" ? "已通过" : row.review === "pending" ? "待审批" : "草稿"}</span></span><button className="row-action" onClick={() => setDetailRow(row)} type="button">查看</button></div>)}
        </section>
        <div className="kb-list-footer"><span className="foot">知识与审批数据来自当前店铺；演示文件和检索参数刷新后清空</span><div className="kb-pagination"><button className="btn" disabled={page <= 1} onClick={() => setPage((value) => value - 1)} type="button">上一页</button><span>第 {page} 页</span><button className="btn" disabled={page * 20 >= total} onClick={() => setPage((value) => value + 1)} type="button">下一页</button></div></div>
        {job ? <div aria-live="polite" className="kb-import-status" role="status">导入任务：{job.status} · {job.succeeded_rows}/{job.total_rows} 成功，{job.failed_rows} 失败</div> : null}
      </main>
    </div>
    {anyDialogOpen ? <div className="backdrop open" onClick={closeDialogs} role="presentation" /> : null}
    {parametersOpen ? <aside aria-label="知识库参数配置" aria-modal="true" className="drawer open" role="dialog"><div className="drawer-head"><h2>☷　知识库参数配置</h2><button aria-label="关闭流程参数" autoFocus className="close" onClick={() => setParametersOpen(false)} type="button">×</button></div><div className="drawer-body">
      <section className="parameter-section"><h3>1. 文档分块 (CHUNKING)</h3><div className="parameter-grid"><label>分块大小<input className="field" max={10000} min={1} onChange={(event) => setParameterDraft((current) => ({ ...current, chunk: Number(event.target.value) }))} type="number" value={parameterDraft.chunk} /></label><label>重叠大小<input className="field" max={9999} min={0} onChange={(event) => setParameterDraft((current) => ({ ...current, overlap: Number(event.target.value) }))} type="number" value={parameterDraft.overlap} /></label></div><p className="parameter-hint">分块大小和重叠可在此调整；重叠必须小于分块大小。保存仅作用于本页演示。</p></section>
      <section className="parameter-section"><h3>2. 索引模型 (EMBEDDING)</h3><select aria-label="索引模型" className="field" onChange={(event) => setParameterDraft((current) => ({ ...current, model: event.target.value }))} value={parameterDraft.model}><option value={configuredModel}>{configuredModel} · 当前项目配置</option></select><p className="parameter-hint">下拉仅列出当前项目已配置的索引模型。</p></section>
      <section className="parameter-section"><h3>3. 检索策略 (RETRIEVAL)</h3><div className="range-head"><label htmlFor="kbTopK">单次召回数量 (Top-K)</label><output>{parameterDraft.topK}</output></div><input id="kbTopK" max={50} min={1} onChange={(event) => setParameterDraft((current) => ({ ...current, topK: Number(event.target.value) }))} type="range" value={parameterDraft.topK} /><div className="range-head"><label htmlFor="kbScore">相似度阈值 (Score Threshold)</label><output>{parameterDraft.score.toFixed(2)}</output></div><input id="kbScore" max={1} min={0} onChange={(event) => setParameterDraft((current) => ({ ...current, score: Number(event.target.value) }))} step={0.01} type="range" value={parameterDraft.score} /></section>
      <section className="parameter-section"><h3>4. 高级策略 (ADVANCED)</h3><div className="rerank-row"><label htmlFor="kbRerank">启用 Rerank 重排</label><label className="switch"><input aria-label="启用 Rerank 重排" checked={parameterDraft.rerank} id="kbRerank" onChange={(event) => setParameterDraft((current) => ({ ...current, rerank: event.target.checked }))} type="checkbox" /><span className="slider" /></label></div><select aria-label="Rerank 模型" className="field" defaultValue={parameterDraft.rerankModel} disabled={!parameterDraft.rerank}><option value="BAAI/bge-reranker-large">BAAI/bge-reranker-large</option></select></section>
      <div className="math-preview"><strong>当前检索逻辑：</strong><p>Dense 相似度 ≥ <b>{parameterDraft.score.toFixed(2)}</b><br />召回前 <b>{parameterDraft.topK}</b> 条候选；启用重排后展示前 5 条。</p></div><p className="prototype-note">仅在当前页面模拟参数保存，不会修改项目实际检索策略。</p>
    </div><div className="drawer-foot"><button className="btn" onClick={() => setParametersOpen(false)} type="button">取消</button><button className="btn primary" onClick={saveParameters} type="button">保存并应用</button></div></aside> : null}
    {detailRow ? <aside aria-label="知识详情" aria-modal="true" className="drawer detail-drawer open" role="dialog"><div className="drawer-head"><h2>知识详情</h2><button aria-label="关闭知识详情" autoFocus className="close" onClick={() => setDetailRow(null)} type="button">×</button></div><div className="drawer-body">
      <div className="detail-heading"><span className={`file-icon ${detailRow.type}`}>{detailRow.type === "pdf" ? "PDF" : detailRow.type === "xlsx" ? "X" : "TXT"}</span><strong>{detailRow.title}</strong><span className={`badge ${detailRow.review === "approved" ? "ok" : "wait"}`}>{detailApproval}</span></div>
      <div className="detail-meta"><div className="detail-meta-row"><span>所属分类</span><strong>{detailCategory}</strong></div><div className="detail-meta-row"><span>当前版本</span><strong>v{detailRow.version}<small>{knowledgeDate(detailRow.updated)} 更新</small></strong></div><div className="detail-meta-row"><span>适用范围</span><strong>{storeName}</strong></div><div className="detail-meta-row"><span>语义类型</span><strong>{detailSemantic}</strong></div><div className="detail-meta-row"><span>文件来源</span><strong>{detailRow.demo ? detailRow.demo.file.name : detailRow.entry?.source ?? "未记录"}</strong></div><div className="detail-meta-row"><span>创建人</span><strong>—</strong></div><div className="detail-meta-row"><span>最后更新</span><strong>{knowledgeDate(detailRow.updated)}</strong></div></div>
      <section className="detail-section detail-summary"><h3>内容摘要</h3><p>{detailRow.entry?.answer ?? "页面演示文件未经过服务端解析，暂无可展示的内容摘要。"}</p></section>
      {detailRow.demo ? <section className="detail-section detail-file-section"><h3>关联文件 · 页面演示</h3><div className="detail-file"><span className={`file-icon ${detailRow.type}`}>{detailRow.type === "pdf" ? "PDF" : detailRow.type === "xlsx" ? "X" : "TXT"}</span><div className="detail-file-info"><strong>{detailRow.demo.file.name}</strong><small>{(detailRow.demo.file.size / 1024).toFixed(1)} KB</small></div><button aria-label="下载关联文件" className="detail-download" onClick={() => { const url = URL.createObjectURL(detailRow.demo!.file); const anchor = document.createElement("a"); anchor.href = url; anchor.download = detailRow.demo!.file.name; anchor.click(); window.setTimeout(() => URL.revokeObjectURL(url), 60000); }} title="下载关联文件" type="button">⇩</button></div></section> : null}
      <div className="detail-note"><span className="detail-note-icon">ⓘ</span><div><strong>使用说明</strong><span>本知识仅用于 AI 建议生成与坐席人工复核，不支持公开自动回复。请结合实际订单情况与平台最新政策进行判断。</span></div></div>
      {detailRow.entry ? <div className="kb-detail-actions"><button className="btn" onClick={() => { setEditingEntry(detailRow.entry!); setDetailRow(null); setEntryEditorOpen(true); }} type="button">编辑知识</button>{detailRow.entry.status !== "published" ? <button className="btn primary" disabled={detailRow.entry.statement_type === "unknown"} onClick={() => { void publishEntry(detailRow.entry!); setDetailRow(null); }} type="button">审批并发布</button> : null}{detailRow.entry.vectorization_status === "failed" ? <button className="btn" onClick={() => { void retryVectorization(detailRow.entry!); setDetailRow(null); }} type="button">重试向量化</button> : null}{detailRow.entry.status !== "archived" ? <button className="btn" onClick={() => { void archiveEntry(detailRow.entry!); setDetailRow(null); }} type="button">归档</button> : null}<button className="btn" onClick={() => { void removeEntry(detailRow.entry!); setDetailRow(null); }} type="button">删除</button></div> : null}
    </div></aside> : null}
    {categoryEditorOpen ? <div aria-label={editingCategory ? "编辑分类" : "新增知识分类"} aria-modal="true" className="modal category-modal open" role="dialog"><div className="modal-head"><h2>{editingCategory ? "编辑分类" : "新增知识分类"}</h2><button aria-label="关闭新增分类" autoFocus className="close" onClick={() => setCategoryEditorOpen(false)} type="button">×</button></div>{categoryForm}{categoryTree.length ? <div className="kb-category-manager"><strong>已有分类</strong>{categoryTree.map((category) => <div className="kb-category-manager-row" key={category.id}><span>{`${"— ".repeat(category.depth)}${category.name}`}</span><button aria-label={`编辑分类：${category.name}`} onClick={() => setEditingCategory(category)} type="button">编辑</button>{customCategories.some((item) => item.id === category.id) ? <button aria-label={`删除分类：${category.name}`} disabled={Boolean(deletingCategoryId)} onClick={() => requestCategoryDelete(category)} type="button">删除</button> : null}</div>)}</div> : null}</div> : null}
    {pendingCategoryDelete ? <div aria-label="删除自定义分类" aria-modal="true" aria-describedby="kb-delete-category-warning" className="modal category-modal open" role="dialog"><div className="modal-head"><h2>删除自定义分类</h2><button aria-label="关闭删除确认" className="close" disabled={Boolean(deletingCategoryId)} onClick={() => setPendingCategoryDelete(null)} type="button">×</button></div><div className="modal-content"><p className="kb-delete-category-copy">确定删除分类 <strong>{pendingCategoryDelete.name}</strong> 吗？</p><p className="kb-delete-category-warning" id="kb-delete-category-warning">仅空分类可以删除。分类下的知识或子分类需先移除；删除后无法恢复。</p></div><div className="modal-foot"><button autoFocus className="btn" disabled={Boolean(deletingCategoryId)} onClick={() => setPendingCategoryDelete(null)} type="button">取消</button><button className="btn danger" disabled={Boolean(deletingCategoryId)} onClick={() => void removeCategory()} type="button">{deletingCategoryId ? "正在删除…" : "删除分类"}</button></div></div> : null}
    {entryEditorOpen ? <div aria-label={editingEntry ? "编辑知识" : "新增知识文档"} aria-modal="true" className="modal open" role="dialog"><div className="modal-head"><h2>{editingEntry ? "编辑知识" : addMode === "manual" ? "手动录入知识" : "新增知识文档"}</h2><button aria-label="关闭新增知识" autoFocus className="close" onClick={() => setEntryEditorOpen(false)} type="button">×</button></div>
      {editingEntry ? entryForm : <><div aria-label="新增知识方式" className="mode-tabs" role="tablist"><button aria-selected={addMode === "upload"} className={`mode-tab${addMode === "upload" ? " active" : ""}`} onClick={() => setAddMode("upload")} role="tab" type="button">上传文档</button><button aria-selected={addMode === "manual"} className={`mode-tab${addMode === "manual" ? " active" : ""}`} onClick={() => setAddMode("manual")} role="tab" type="button">手动录入</button></div>
        {addMode === "manual" ? <form className="kb-modal-form" onSubmit={addEntry}><div className="modal-content manual-fields"><label className="label">知识标题<input className="field" maxLength={120} name="question" placeholder="输入知识标题" required /></label><label className="label">知识内容<textarea className="field" maxLength={10000} name="answer" placeholder="输入供内部审核的知识正文" required rows={7} /></label><p className="parameter-hint">保存为当前店铺草稿；知识语义类型须在审批前补齐。</p><input defaultValue="unknown" name="statement_type" type="hidden" /><input defaultValue="none" name="customer_scope" type="hidden" /><input defaultValue="" name="tags" type="hidden" /><div className="form-row"><label className="label">归属分类<select className="field select" defaultValue={selectedCategoryId} name="category_id"><option value="">未分类</option>{categoryTree.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label></div></div><div className="modal-foot"><button className="btn" onClick={() => setEntryEditorOpen(false)} type="button">取消</button><button className="btn primary" disabled={entrySubmitting} type="submit">保存知识</button></div></form> : <><div className="modal-content"><div aria-label="选择或拖入知识文件" className="upload" onClick={() => fileInputRef.current?.click()} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); chooseFile(event.dataTransfer.files[0]); }} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); fileInputRef.current?.click(); } }} role="button" tabIndex={0}><div className="upload-icon">☁</div><strong>{selectedFile ? `已选择：${selectedFile.name}` : "点击或拖拽文件到此处上传"}</strong><small>{selectedFile ? "CSV/XLSX 调用真实导入；其他格式只加入本页演示列表" : "支持 PDF、Word、Markdown、Excel、TXT（最大 50MB）"}</small></div><div className="form-row"><label className="label">归属分类<select className="field select" onChange={(event) => setSelectedUploadCategoryId(event.target.value)} value={selectedUploadCategoryId}><option value="">未分类</option>{categoryTree.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label><label className="label">分段策略 (Chunking)<select className="field select" onChange={(event) => setSegmentMode(event.target.value)} value={segmentMode}><option value="semantic">按语义自动分段 (推荐)</option><option value="fixed">按固定字符数分段</option></select></label></div><div className="engine-label">解析引擎 (Parser)</div><div className="engines"><button className={`engine${parserMode === "standard" ? " active" : ""}`} onClick={() => setParserMode("standard")} type="button"><strong>◉　通用解析</strong><small>自动提取文本，适合常规文档</small></button><button className={`engine${parserMode === "deep" ? " active" : ""}`} onClick={() => setParserMode("deep")} type="button"><strong>○　深度文档</strong><small>处理复杂表格、多栏排版</small></button></div><div className="switch-line"><span className="switch-copy"><strong>上传后立即进行向量化</strong><small>页面演示开关，不会改变真实服务配置</small></span><label className="switch"><input aria-label="进行向量化" checked={vectorizeAfterUpload} onChange={(event) => setVectorizeAfterUpload(event.target.checked)} type="checkbox" /><span className="slider" /></label></div><p className="prototype-note">CSV/XLSX 使用现有导入接口，分类取文件中的 category_code。其他格式与解析选项仅作页面演示，刷新后清空。</p></div><div className="modal-foot"><button className="btn" onClick={() => setEntryEditorOpen(false)} type="button">取消</button><button className="btn primary" onClick={() => void submitSelectedFile()} type="button">确认上传并解析</button></div></>}
      </>}
    </div> : null}
    {notice ? <div aria-live="polite" className="toast show" role="status">{notice}</div> : null}
  </div></AppShell>;
}
