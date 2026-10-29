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
  archiveDocumentFile,
  createKnowledgeCategory,
  createKnowledgeEntry,
  currentUser,
  deleteKnowledgeCategory,
  deleteKnowledgeEntry,
  deleteDocumentFile,
  downloadDocumentSource,
  getDocumentFile,
  getDocumentSettings,
  getDocumentVersion,
  getImportJob,
  getKnowledgeVectorizationStatus,
  importKnowledge,
  importDocumentFile,
  isAuthenticationError,
  listKnowledgeCategories,
  listKnowledgeEntries,
  listDocumentFiles,
  listStores,
  publishKnowledgeEntry,
  retryKnowledgeVectorization,
  retryDocumentVersion,
  reviewDocumentUnit,
  restoreDocumentFile,
  saveDocumentSettings,
  updateKnowledgeCategory,
  updateKnowledgeEntry,
  updateDocumentFileCategory,
  type ImportJob,
  type DocumentFileDetail,
  type DocumentFileSummary,
  type DocumentIndexConfig,
  type DocumentStrategy,
  type DocumentVersionDetail,
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
type KnowledgeParameters = { strategy: DocumentStrategy; chunk: number; overlap: number; parserMode: DocumentIndexConfig["parser_mode"]; model: DocumentIndexConfig["embedding_model"]; topK: number; score: number; rerank: boolean; rerankModel: "BAAI/bge-reranker-large" };
type KnowledgeRow = { id: string; categoryId: string | null; title: string; type: "pdf" | "xlsx" | "txt"; updated: string; version: number; vector: string; review: "approved" | "pending" | "draft" | "review_required"; entry?: KnowledgeEntry; file?: DocumentFileSummary };

const defaultParameters: KnowledgeParameters = { strategy: "recursive", chunk: 500, overlap: 50, parserMode: "auto", model: "BAAI/bge-m3", topK: 20, score: 0.52, rerank: true, rerankModel: "BAAI/bge-reranker-large" };
const chunkStrategies: Array<{ value: DocumentStrategy; label: string; extensions?: string[] }> = [
  { value: "recursive", label: "按语义结构递归分段（推荐）" },
  { value: "heading_paragraph", label: "按标题与段落分段", extensions: ["pdf", "doc", "docx", "ppt", "pptx", "txt", "md"] },
  { value: "sentence", label: "按句子分段", extensions: ["pdf", "doc", "docx", "ppt", "pptx", "txt", "md", "png", "jpg", "jpeg"] },
  { value: "fixed_token", label: "按固定 Token 数分段" },
  { value: "fixed_char", label: "按固定字符数分段" },
  { value: "semantic_similarity", label: "按语义相似度分段", extensions: ["pdf", "doc", "docx", "ppt", "pptx", "txt", "md", "png", "jpg", "jpeg"] },
  { value: "page_slide", label: "按页或幻灯片分段", extensions: ["pdf", "ppt", "pptx"] },
  { value: "ocr_layout", label: "按 OCR 版面分段", extensions: ["pdf", "png", "jpg", "jpeg"] },
  { value: "table_rows", label: "按表格行分段", extensions: ["xls", "xlsx", "csv", "tsv", "pdf", "doc", "docx", "ppt", "pptx"] },
];
const documentExtensions = ["csv", "tsv", "xlsx", "xls", "pdf", "doc", "docx", "ppt", "pptx", "md", "txt", "png", "jpg", "jpeg"];

function documentConfig(parameters: KnowledgeParameters, strategy = parameters.strategy, parserMode = parameters.parserMode): DocumentIndexConfig {
  return { strategy, chunk_size: parameters.chunk, overlap: strategy === "table_rows" ? 0 : parameters.overlap, parser_mode: parserMode, embedding_model: parameters.model };
}

function strategySupportsFile(strategy: DocumentStrategy, filename: string): boolean {
  const rule = chunkStrategies.find((item) => item.value === strategy);
  const extension = filename.split(".").pop()?.toLowerCase() ?? "";
  return Boolean(rule && (!rule.extensions || rule.extensions.includes(extension)));
}

function documentStatusText(status: string): string {
  return ({ queued: "排队中", parsing: "解析中", review_required: "待复核", indexing: "向量化中", ready: "索引完成", failed_retryable: "可重试失败", failed_final: "处理失败" } as Record<string, string>)[status] ?? status;
}
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

function knowledgeIconLabel(row: KnowledgeRow): string {
  if (row.file) return row.file.filename.split(".").pop()?.toUpperCase().slice(0, 4) ?? "FILE";
  return row.type === "pdf" ? "PDF" : row.type === "xlsx" ? "X" : "TXT";
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
  const [documentFiles, setDocumentFiles] = useState<DocumentFileSummary[]>([]);
  const [documentTotal, setDocumentTotal] = useState(0);
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
  const [fileDetail, setFileDetail] = useState<DocumentFileDetail | null>(null);
  const [versionDetail, setVersionDetail] = useState<DocumentVersionDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [reviewDrafts, setReviewDrafts] = useState<Record<number, string>>({});
  const [reviewSubmitting, setReviewSubmitting] = useState(false);
  const [parametersOpen, setParametersOpen] = useState(false);
  const [parameters, setParameters] = useState<KnowledgeParameters>(defaultParameters);
  const [parameterDraft, setParameterDraft] = useState<KnowledgeParameters>(defaultParameters);
  const [fileTypeFilter, setFileTypeFilter] = useState("");
  const [vectorFilter, setVectorFilter] = useState("");
  const [reviewFilter, setReviewFilter] = useState("");
  const [addMode, setAddMode] = useState<"upload" | "manual">("upload");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedUploadCategoryId, setSelectedUploadCategoryId] = useState("");
  const [segmentMode, setSegmentMode] = useState<DocumentStrategy>("recursive");
  const [parserMode, setParserMode] = useState<DocumentIndexConfig["parser_mode"]>("auto");
  const [uploadKind, setUploadKind] = useState<"document" | "faq">("document");
  const [uploadSubmitting, setUploadSubmitting] = useState(false);
  const [pendingReplacement, setPendingReplacement] = useState<DocumentFileSummary | null>(null);
  const [replacementTarget, setReplacementTarget] = useState<DocumentFileSummary | null>(null);
  const [editingFile, setEditingFile] = useState<DocumentFileSummary | null>(null);
  const [fileCategoryDraft, setFileCategoryDraft] = useState("");
  const [pendingFileAction, setPendingFileAction] = useState<{ file: DocumentFileSummary; action: "archive" | "restore" | "delete" } | null>(null);
  const [fileActionSubmitting, setFileActionSubmitting] = useState(false);
  const [categoryEditorOpen, setCategoryEditorOpen] = useState(false);
  const [entryEditorOpen, setEntryEditorOpen] = useState(false);
  const [categorySubmitting, setCategorySubmitting] = useState(false);
  const [deletingCategoryId, setDeletingCategoryId] = useState<string | null>(null);
  const [pendingCategoryDelete, setPendingCategoryDelete] = useState<KnowledgeCategory | null>(null);
  const [categoryReloadRevision, setCategoryReloadRevision] = useState(0);
  const [entrySubmitting, setEntrySubmitting] = useState(false);
  const loadRequestId = useRef(0);
  const detailRequestId = useRef(0);
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
    const fileRows = documentFiles.filter((file) => !isEmptyPreset && file.store_id === storeId && (!effectiveCategoryId || file.category_id === effectiveCategoryId)).map((file): KnowledgeRow => ({
      id: file.id,
      categoryId: file.category_id,
      title: file.filename,
      type: knowledgeFileType(file.filename),
      updated: file.latest_version.created_at,
      version: file.latest_version.version_number,
      vector: file.latest_version.status === "ready" ? "ready" : file.latest_version.status === "review_required" ? "review_required" : file.latest_version.status.startsWith("failed") ? "failed" : "pending",
      review: file.latest_version.status === "review_required" ? "review_required" : file.latest_version.status === "ready" ? "approved" : "pending",
      file,
    }));
    return [...fileRows, ...realRows].filter((row) => {
      return (!fileTypeFilter || row.type === fileTypeFilter) && (!vectorFilter || row.vector === vectorFilter) && (!reviewFilter || row.review === reviewFilter);
    });
  }, [documentFiles, effectiveCategoryId, entries, fileTypeFilter, isEmptyPreset, reviewFilter, storeId, vectorFilter]);

  const load = useCallback(async (silent = false) => {
    if (!storeId) return;
    const requestId = ++loadRequestId.current;
    if (!silent) setLoading(true);
    setError("");
    try {
      const query = new URLSearchParams({ page: String(page), page_size: "20", store_id: storeId, categorized_only: "true" });
      if (search) query.set("search", search);
      if (status) query.set("status", status);
      if (effectiveCategoryId) query.set("category_id", effectiveCategoryId);
      const [categoryData, entryData, fileData] = await Promise.all([
        listKnowledgeCategories(storeId),
        isEmptyPreset ? Promise.resolve({ items: [] as KnowledgeEntry[], page, page_size: 20, total: 0 }) : listKnowledgeEntries(query),
        isEmptyPreset ? Promise.resolve({ items: [] as DocumentFileSummary[], page, page_size: 20, total: 0 }) : listDocumentFiles(new URLSearchParams(query)),
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
      setDocumentFiles(fileData.items);
      setDocumentTotal(fileData.total);
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
    let active = true;
    void getDocumentSettings(storeId).then((config) => {
      if (!active) return;
      setParameters((current) => ({ ...current, strategy: config.strategy, chunk: config.chunk_size, overlap: config.overlap, parserMode: config.parser_mode, model: config.embedding_model }));
    }).catch((caught: unknown) => {
      if (active) setNotice(caught instanceof Error ? caught.message : "导入参数加载失败");
    });
    return () => { active = false; };
  }, [storeId]);

  useEffect(() => {
    if (!storeId) return;
    let active = true;
    void getKnowledgeVectorizationStatus(storeId).then((value) => { if (active) setVectorizationStatus(value); }).catch(() => { if (active) setVectorizationStatus(null); });
    return () => { active = false; };
  }, [storeId, countRevision]);

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
          const query = new URLSearchParams({ page: "1", page_size: "1", store_id: storeId, categorized_only: "true" });
          if (id) query.set("category_id", id);
          try {
            const [faq, files] = await Promise.all([listKnowledgeEntries(query), listDocumentFiles(new URLSearchParams(query))]);
            return { id, total: faq.total + files.total };
          }
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
    if (!documentFiles.some((file) => ["queued", "parsing", "indexing"].includes(file.latest_version.status))) return;
    const timer = window.setInterval(() => { void load(true); }, 2500);
    return () => window.clearInterval(timer);
  }, [documentFiles, load]);

  useEffect(() => {
    const fileId = detailRow?.file?.id;
    const versionNumber = versionDetail?.version_number;
    if (!fileId || !versionNumber || !versionDetail || !["queued", "parsing", "indexing"].includes(versionDetail.status)) return;
    const requestId = detailRequestId.current;
    const timer = window.setInterval(() => {
      void Promise.all([getDocumentFile(fileId), getDocumentVersion(fileId, versionNumber)]).then(([file, version]) => {
        if (requestId !== detailRequestId.current) return;
        setFileDetail(file);
        setVersionDetail(version);
      }).catch(() => {
        if (requestId === detailRequestId.current) setNotice("文件状态暂时无法刷新");
      });
    }, 2500);
    return () => window.clearInterval(timer);
  }, [detailRow, versionDetail]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || deletingCategoryId || fileActionSubmitting) return;
      detailRequestId.current += 1;
      setParametersOpen(false);
      setDetailRow(null);
      setFileDetail(null);
      setVersionDetail(null);
      setPendingReplacement(null);
      setReplacementTarget(null);
      setCategoryEditorOpen(false);
      setEntryEditorOpen(false);
      setPendingCategoryDelete(null);
      setEditingFile(null);
      setPendingFileAction(null);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [deletingCategoryId, fileActionSubmitting]);

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

  async function openKnowledgeRow(row: KnowledgeRow) {
    const requestId = ++detailRequestId.current;
    setDetailRow(row);
    setFileDetail(null);
    setVersionDetail(null);
    if (!row.file) return;
    setDetailLoading(true);
    try {
      const [file, version] = await Promise.all([
        getDocumentFile(row.file.id),
        getDocumentVersion(row.file.id, row.file.latest_version.version_number),
      ]);
      if (requestId !== detailRequestId.current) return;
      setFileDetail(file);
      setVersionDetail(version);
      setReviewDrafts(Object.fromEntries(version.units.map((unit) => [unit.unit_index, unit.cleaned_text])));
    } catch (caught) {
      if (requestId === detailRequestId.current) setNotice(caught instanceof Error ? caught.message : "文件详情加载失败");
    } finally {
      if (requestId === detailRequestId.current) setDetailLoading(false);
    }
  }

  async function selectDocumentVersion(versionNumber: number) {
    if (!fileDetail) return;
    const requestId = ++detailRequestId.current;
    setDetailLoading(true);
    try {
      const version = await getDocumentVersion(fileDetail.id, versionNumber);
      if (requestId !== detailRequestId.current) return;
      setVersionDetail(version);
      setReviewDrafts(Object.fromEntries(version.units.map((unit) => [unit.unit_index, unit.cleaned_text])));
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : "版本详情加载失败");
    } finally {
      if (requestId === detailRequestId.current) setDetailLoading(false);
    }
  }

  async function submitReview(unitIndex: number) {
    if (!versionDetail || reviewSubmitting) return;
    const corrected = reviewDrafts[unitIndex]?.trim();
    if (!corrected) { setNotice("请补全修订内容再确认"); return; }
    setReviewSubmitting(true);
    try {
      const updated = await reviewDocumentUnit(versionDetail.file_id, versionDetail.version_number, unitIndex, corrected);
      setVersionDetail(updated);
      setNotice(updated.status === "queued" ? "全部问题单元已确认，整版重新进入索引队列" : "该单元已确认，整版仍待复核");
      await load(true);
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : "复核提交失败");
    } finally {
      setReviewSubmitting(false);
    }
  }

  async function retryFileVersion() {
    if (!versionDetail || reviewSubmitting) return;
    setReviewSubmitting(true);
    try {
      const updated = await retryDocumentVersion(versionDetail.file_id, versionDetail.version_number);
      setVersionDetail(updated);
      setNotice("文件版本已重新进入处理队列");
      await load(true);
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : "重试失败");
    } finally {
      setReviewSubmitting(false);
    }
  }

  async function downloadOriginal() {
    if (!versionDetail) return;
    try {
      const blob = await downloadDocumentSource(versionDetail.file_id, versionDetail.version_number);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = versionDetail.filename;
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : "原文件下载失败");
    }
  }

  async function upload(file: File | undefined): Promise<boolean> {
    if (!file || !storeId || uploadSubmitting) return false;
    setUploadSubmitting(true);
    try {
      const accepted = await importKnowledge(storeId, file);
      setJob(await getImportJob(accepted.job_id));
      setNotice(en ? "File queued for import" : "文件已进入异步导入队列");
      return true;
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : (en ? "Import failed" : "导入失败"));
      return false;
    } finally {
      setUploadSubmitting(false);
    }
  }

  function chooseFile(file: File | undefined) {
    if (!file) return;
    if (replacementTarget && file.name.toLocaleLowerCase() !== replacementTarget.filename.toLocaleLowerCase()) {
      setNotice(`替换文件须保持原文件名：${replacementTarget.filename}`);
      return;
    }
    const extension = file.name.split(".").pop()?.toLowerCase();
    if (!extension || !documentExtensions.includes(extension)) {
      setNotice("请选择支持的文件格式");
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      setNotice("单个通用文档不能超过 20 MiB");
      return;
    }
    setSelectedFile(file);
    if (!["csv", "xlsx"].includes(extension)) setUploadKind("document");
    if (!strategySupportsFile(segmentMode, file.name)) setSegmentMode("recursive");
    if (parserMode === "basic" && !["pdf", "png", "jpg", "jpeg"].includes(extension)) setParserMode("auto");
  }

  async function performDocumentUpload(replaceFileId: string | null) {
    if (!selectedFile || !storeId || uploadSubmitting) return;
    if (!selectedUploadCategoryId) { setNotice("请先选择归属分类"); return; }
    setUploadSubmitting(true);
    try {
      const accepted = await importDocumentFile(storeId, selectedFile, documentConfig(parameters, segmentMode, parserMode), selectedUploadCategoryId || null, replaceFileId);
      setNotice(`文件 v${accepted.version_number} 已进入解析队列；处理状态会自动更新`);
      setPendingReplacement(null);
      setReplacementTarget(null);
      setEntryEditorOpen(false);
      setSelectedFile(null);
      setSearch("");
      setFileTypeFilter("");
      setVectorFilter("");
      setReviewFilter("");
      setPage(1);
      setCountRevision((value) => value + 1);
      await load(true);
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : "文件上传失败");
    } finally {
      setUploadSubmitting(false);
    }
  }

  async function submitSelectedFile() {
    if (!selectedFile || !storeId) {
      setNotice("请先选择知识文件");
      return;
    }
    const extension = selectedFile.name.split(".").pop()?.toLowerCase();
    if (uploadKind === "faq") {
      if (replacementTarget) { setNotice("替换通用文件不能切换为 FAQ 导入"); return; }
      if (extension !== "csv" && extension !== "xlsx") { setNotice("FAQ 批量导入仅支持 CSV/XLSX"); return; }
      if (selectedFile.size > 10 * 1024 * 1024) { setNotice("FAQ 表格不能超过 10 MiB"); return; }
      if (!await upload(selectedFile)) return;
      setNotice("FAQ 表格已提交现有导入队列；分类取文件中的 category_code");
      setEntryEditorOpen(false);
      setSelectedFile(null);
    } else {
      if (replacementTarget?.store_id !== undefined && replacementTarget.store_id !== storeId) { setNotice("替换目标不属于当前店铺"); return; }
      if (!selectedUploadCategoryId) { setNotice("请先选择归属分类"); return; }
      if (!strategySupportsFile(segmentMode, selectedFile.name)) { setNotice("该文件格式不适用当前分块策略"); return; }
      if (parserMode === "basic" && !["pdf", "png", "jpg", "jpeg"].includes(extension ?? "")) { setNotice("Basic OCR 仅适用于 PDF 和图片"); return; }
      if (replacementTarget) {
        if (selectedFile.name.toLocaleLowerCase() !== replacementTarget.filename.toLocaleLowerCase()) { setNotice("替换文件须保持原文件名"); return; }
        setPendingReplacement(replacementTarget);
        setEntryEditorOpen(false);
        return;
      }
      setUploadSubmitting(true);
      try {
        const query = new URLSearchParams({ store_id: storeId, search: selectedFile.name, page: "1", page_size: "100" });
        let existing: DocumentFileSummary | undefined;
        do {
          const result = await listDocumentFiles(query);
          existing = result.items.find((file) => file.filename.toLocaleLowerCase() === selectedFile.name.toLocaleLowerCase());
          if (existing || result.page * result.page_size >= result.total) break;
          query.set("page", String(result.page + 1));
        } while (true);
        if (existing) {
          if (existing.archived_at) {
            setNotice("同名文件已归档，请先恢复，再替换");
            return;
          }
          setSelectedUploadCategoryId(existing.category_id ?? "");
          setPendingReplacement(existing);
          setEntryEditorOpen(false);
          return;
        }
        await performDocumentUpload(null);
      } catch (caught) {
        setNotice(caught instanceof Error ? caught.message : "检查同名文件失败");
      } finally {
        setUploadSubmitting(false);
      }
      return;
    }
    setSearch("");
    setFileTypeFilter("");
    setVectorFilter("");
    setReviewFilter("");
    setPage(1);
  }

  async function saveFileCategory() {
    if (!editingFile || editingFile.store_id !== storeId || !fileCategoryDraft || fileActionSubmitting) return;
    setFileActionSubmitting(true);
    try {
      await updateDocumentFileCategory(editingFile.id, fileCategoryDraft);
      setEditingFile(null);
      setNotice("文件分类已更新，原版本保持不变");
      setSelectedCategoryId(fileCategoryDraft);
      setSelectedEmptyPreset("");
      setPage(1);
      setCountRevision((value) => value + 1);
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : "调整分类失败");
    } finally { setFileActionSubmitting(false); }
  }

  async function applyFileAction() {
    if (!pendingFileAction || pendingFileAction.file.store_id !== storeId || fileActionSubmitting) return;
    const { file, action } = pendingFileAction;
    setFileActionSubmitting(true);
    try {
      if (action === "archive") await archiveDocumentFile(file.id);
      else if (action === "restore") await restoreDocumentFile(file.id);
      else await deleteDocumentFile(file.id);
      setPendingFileAction(null);
      setNotice(action === "archive" ? "文件已归档" : action === "restore" ? "文件已恢复" : "文件已删除");
      setCountRevision((value) => value + 1);
      await load(true);
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : "文件操作失败");
    } finally { setFileActionSubmitting(false); }
  }

  function openAdd() {
    if (isEmptyPreset && selectedPreset) {
      setEditingCategory(null);
      setCategoryEditorOpen(true);
      setNotice(`请先将“${selectedPreset.name}”保存到当前店铺，再添加知识`);
      return;
    }
    setEditingEntry(null);
    setReplacementTarget(null);
    setSelectedFile(null);
    setSelectedUploadCategoryId(selectedCategoryId);
    setSegmentMode(parameters.strategy);
    setParserMode(parameters.parserMode);
    setUploadKind("document");
    setAddMode("upload");
    setEntryEditorOpen(true);
  }

  async function saveParameters() {
    if (!Number.isInteger(parameterDraft.chunk) || parameterDraft.chunk < 32 || parameterDraft.chunk > 10000 || !Number.isInteger(parameterDraft.overlap) || parameterDraft.overlap < 0 || parameterDraft.overlap >= parameterDraft.chunk || (parameterDraft.strategy === "table_rows" && parameterDraft.overlap !== 0)) {
      setNotice("请检查分块大小与重叠大小");
      return;
    }
    try {
      await saveDocumentSettings(storeId, documentConfig(parameterDraft));
      setParameters(parameterDraft);
      setParametersOpen(false);
      setNotice("文档导入参数已保存到当前店铺；检索参数仅作页面演示");
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : "保存参数失败");
    }
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
      <div className="form-row"><label className="label">归属分类<select className="field" defaultValue={editingEntry?.category_id ?? selectedCategoryId} name="category_id" required><option value="">请选择分类</option>{categoryTree.map((category) => <option key={category.id} value={category.id}>{`${"— ".repeat(category.depth)}${category.name}`}</option>)}</select></label><label className="label">标签（逗号分隔）<input className="field" defaultValue={editingEntry?.tags.join(", ")} name="tags" /></label></div>
      <p className="parameter-hint">内容或语义范围修改后会生成新版本，并撤销原审批。</p>
    </div>
    <div className="modal-foot"><button className="btn" onClick={() => setEntryEditorOpen(false)} type="button">取消</button><button className="btn primary" disabled={!storeId || entrySubmitting} type="submit">{entrySubmitting ? "正在保存…" : editingEntry ? "保存修改" : "保存知识"}</button></div>
  </form>;

  const closeDialogs = () => { if (deletingCategoryId || fileActionSubmitting) return; detailRequestId.current += 1; setParametersOpen(false); setDetailRow(null); setFileDetail(null); setVersionDetail(null); setCategoryEditorOpen(false); setEntryEditorOpen(false); setPendingCategoryDelete(null); setPendingReplacement(null); setReplacementTarget(null); setEditingFile(null); setPendingFileAction(null); };
  const changeStore = (nextStoreId: string) => {
    if (nextStoreId === storeId) return;
    // 店铺切换先终止旧上下文；异步详情和列表响应不能重新打开旧店铺数据。
    loadRequestId.current += 1;
    detailRequestId.current += 1;
    setDetailRow(null);
    setFileDetail(null);
    setVersionDetail(null);
    setDetailLoading(false);
    setReviewDrafts({});
    setParametersOpen(false);
    setCategoryEditorOpen(false);
    setEditingCategory(null);
    setEntryEditorOpen(false);
    setEditingEntry(null);
    setPendingCategoryDelete(null);
    setPendingReplacement(null);
    setReplacementTarget(null);
    setEditingFile(null);
    setPendingFileAction(null);
    setSelectedFile(null);
    setSelectedUploadCategoryId("");
    setJob(null);
    setCategories([]);
    setEntries([]);
    setDocumentFiles([]);
    setTotal(0);
    setDocumentTotal(0);
    setCategoryCounts({});
    setAllCategoryCount(null);
    setVectorizationStatus(null);
    setLoading(true);
    setStoreId(nextStoreId);
    setSelectedCategoryId("");
    setSelectedEmptyPreset("");
    setSearch("");
    setStatus("");
    setFileTypeFilter("");
    setVectorFilter("");
    setReviewFilter("");
    setPage(1);
  };
  const anyDialogOpen = parametersOpen || Boolean(detailRow) || categoryEditorOpen || entryEditorOpen || Boolean(pendingCategoryDelete) || Boolean(pendingReplacement) || Boolean(editingFile) || Boolean(pendingFileAction);
  const scopeDescription = selectedPreset?.description ?? (selectedCategory ? "当前店铺新增的自定义知识分类。" : "查看当前店铺的全部知识文档，供客服参考使用。");
  const scopeServerCount = isEmptyPreset ? 0 : effectiveCategoryId ? categoryCounts[effectiveCategoryId] ?? total + documentTotal : allCategoryCount ?? total + documentTotal;
  const categoryCountLabel = (categoryId: string | undefined): string => {
    if (!categoryId) return "0";
    const count = categoryCounts[categoryId];
    if (count === undefined) return "…";
    if (count === null) return "—";
    return String(count);
  };
  const detailCategory = detailRow ? categories.find((category) => category.id === detailRow.categoryId)?.name ?? "未分类" : "";
  const detailApproval = detailRow?.file ? detailRow.file.archived_at ? "已归档" : versionDetail?.status === "ready" ? "索引完成" : versionDetail?.status === "review_required" ? "待复核" : "处理中" : detailRow?.review === "approved" ? "已通过" : detailRow?.review === "pending" ? "待审批" : "草稿";
  const detailSemantic = detailRow?.entry ? statementTypes.find((item) => item.value === detailRow.entry?.statement_type)?.[en ? "en" : "zh"] ?? "未分类" : "文档索引 · 审批并绑定后可供 Agent 检索";

  return <AppShell><div className="knowledge-page">
    <input accept=".csv,.tsv,.xlsx,.xls,.pdf,.doc,.docx,.ppt,.pptx,.md,.txt,.png,.jpg,.jpeg" aria-label="选择知识文件" disabled={!storeId} hidden onChange={(event) => { chooseFile(event.target.files?.[0]); event.target.value = ""; }} ref={fileInputRef} type="file" />
    <header className="topbar">
      <div className="title"><span className="title-icon" aria-hidden="true">▣</span><div><h1>知识库</h1><p>管理客服建议使用的内部知识</p></div></div>
      <div className="top-actions">
        <label className="store">▣ 当前店铺：<select aria-label="当前店铺" disabled={!stores.length || categorySubmitting || Boolean(deletingCategoryId) || entrySubmitting || uploadSubmitting || reviewSubmitting || fileActionSubmitting || Boolean(retryingEntryId)} onChange={(event) => changeStore(event.target.value)} value={storeId}>{stores.map((id) => <option key={id} value={id}>{storeDetails.find((store) => store.id === id)?.name ?? id.slice(0, 8)}</option>)}</select></label>
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
        <section className="scope"><div className="scope-copy"><span className="scope-icon" aria-hidden="true">▣</span><div><h2>{selectedScopeLabel}</h2><p>{scopeDescription}</p></div></div><span className="total">{scopeServerCount} 篇知识</span></section>
        <div className="safety">ⓘ　仅供内部客服辅助使用 · 坐席确认后发送</div>
        <div className="config-summary">导入策略：{chunkStrategies.find((item) => item.value === parameters.strategy)?.label}　·　分块：{parameters.chunk}　·　重叠：{parameters.overlap}　·　模型：{parameters.model}　·　FAQ 待向量化：{vectorizationStatus?.counts.pending ?? "—"}　·　文档检索需内部审批并绑定 Agent</div>
        <div className="toolbar"><label className="search"><span aria-hidden="true">⌕</span><input aria-label="搜索知识" className="field" maxLength={200} onChange={(event) => { setPage(1); setSearch(event.target.value); }} placeholder="搜索知识名称或关键词" value={search} /></label>
          <select aria-label="文件类型" className="field filter" onChange={(event) => setFileTypeFilter(event.target.value)} value={fileTypeFilter}><option value="">全部类型</option><option value="pdf">PDF</option><option value="xlsx">Excel</option><option value="txt">其他格式/文本</option></select>
          <select aria-label="向量状态" className="field filter" onChange={(event) => setVectorFilter(event.target.value)} value={vectorFilter}><option value="">向量状态</option><option value="ready">已就绪</option><option value="pending">待处理</option><option value="review_required">待复核</option><option value="disabled">未启用</option><option value="failed">失败</option></select>
          <select aria-label="处理或审批状态" className="field filter" onChange={(event) => setReviewFilter(event.target.value)} value={reviewFilter}><option value="">处理/审批状态</option><option value="approved">已完成</option><option value="review_required">待复核</option><option value="pending">待处理</option><option value="draft">草稿</option></select>
        </div>
        <section aria-label="知识文档列表" className="table"><div className="table-head"><span>文件名称</span><span>更新时间</span><span>向量状态</span><span>处理/审批状态</span><span>操作</span></div>
          {loading ? <div className="empty"><LoadingState /></div> : error ? <div className="empty"><ErrorState message={error} retry={() => void load()} /></div> : !storeId ? <div className="empty" role="status">请先创建店铺，再管理知识。<br /><Link className="btn" href="/settings/stores">创建店铺</Link></div> : !rows.length ? <div className="empty"><EmptyState label="当前条件下没有知识文档" /></div> : rows.map((row) => <div className="row" key={`${row.file ? "file" : "faq"}-${row.id}`}><div className="file"><span className={`file-icon ${row.type}`}>{knowledgeIconLabel(row)}</span><div className="kb-file-copy"><strong title={row.title}>{row.title}</strong><small>{row.file ? `文档索引 · v${row.version} · ${row.file.latest_version.chunk_count} 块` : `FAQ · v${row.version} · ${row.entry?.source ?? "内部知识"}`}</small></div></div><span className="kb-updated">{knowledgeDate(row.updated)}</span><span className="state"><i className={`dot${row.vector === "ready" && !row.file?.archived_at ? "" : " wait"}`} />{row.file?.archived_at ? "已归档" : row.vector === "ready" ? "已就绪" : row.vector === "review_required" ? "待复核 · 0 新向量" : row.vector === "pending" || row.vector === "processing" ? "待处理" : row.vector === "failed" ? "失败" : "未启用"}</span><span><span className={`badge ${row.file?.archived_at ? "draft" : row.review === "approved" ? "ok" : row.review === "pending" || row.review === "review_required" ? "wait" : "draft"}`}>{row.file?.archived_at ? "已归档" : row.file ? row.review === "approved" ? "索引完成" : row.review === "review_required" ? "待复核" : row.vector === "failed" ? "失败" : "处理中" : row.review === "approved" ? "已通过" : row.review === "pending" ? "待审批" : "草稿"}</span></span><button className="row-action" onClick={() => void openKnowledgeRow(row)} type="button">查看</button></div>)}
        </section>
        <div className="kb-list-footer"><span className="foot">FAQ 与文档数据来自当前店铺；类型和状态筛选作用于当前页；已审批并绑定的文档可供 Agent 检索</span><div className="kb-pagination"><button className="btn" disabled={page <= 1} onClick={() => setPage((value) => value - 1)} type="button">上一页</button><span>第 {page} 页</span><button className="btn" disabled={page * 20 >= Math.max(total, documentTotal)} onClick={() => setPage((value) => value + 1)} type="button">下一页</button></div></div>
        {job ? <div aria-live="polite" className="kb-import-status" role="status">导入任务：{job.status} · {job.succeeded_rows}/{job.total_rows} 成功，{job.failed_rows} 失败</div> : null}
      </main>
    </div>
    {anyDialogOpen ? <div className="backdrop open" onClick={closeDialogs} role="presentation" /> : null}
    {parametersOpen ? <aside aria-label="知识库参数配置" aria-modal="true" className="drawer open" role="dialog"><div className="drawer-head"><h2>☷　知识库参数配置</h2><button aria-label="关闭流程参数" autoFocus className="close" onClick={() => setParametersOpen(false)} type="button">×</button></div><div className="drawer-body">
      <section className="parameter-section"><h3>1. 文档解析与分块 (CHUNKING)</h3><label className="label">分段策略<select aria-label="默认分段策略" className="field" onChange={(event) => { const strategy = event.target.value as DocumentStrategy; setParameterDraft((current) => ({ ...current, strategy, chunk: strategy === "fixed_char" ? 1000 : 500, overlap: strategy === "table_rows" ? 0 : strategy === "fixed_char" ? 100 : 50 })); }} value={parameterDraft.strategy}>{chunkStrategies.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label><div className="parameter-grid"><label>分块大小<input className="field" max={10000} min={32} onChange={(event) => setParameterDraft((current) => ({ ...current, chunk: Number(event.target.value) }))} type="number" value={parameterDraft.chunk} /></label><label>重叠大小<input className="field" disabled={parameterDraft.strategy === "table_rows"} max={9999} min={0} onChange={(event) => setParameterDraft((current) => ({ ...current, overlap: Number(event.target.value) }))} type="number" value={parameterDraft.overlap} /></label></div><p className="parameter-hint">这些值会保存为当前店铺未来导入的默认值；每个文件上传时冻结快照。表格行分段重叠固定为 0。</p><label className="label kb-extra-field">解析档位<select aria-label="默认解析档位" className="field" onChange={(event) => setParameterDraft((current) => ({ ...current, parserMode: event.target.value as DocumentIndexConfig["parser_mode"] }))} value={parameterDraft.parserMode}><option value="auto">自动：文本优先，必要时 OCR</option><option value="flash">Flash：常规文本解析</option><option value="basic">Basic OCR：仅 PDF/图片</option></select></label></section>
      <section className="parameter-section"><h3>2. 索引模型 (EMBEDDING)</h3><select aria-label="索引模型" className="field" value={parameterDraft.model} disabled><option value="BAAI/bge-m3">BAAI/bge-m3 · 当前项目配置</option></select><p className="parameter-hint">文件完成清洗与分块后实际调用当前项目配置的 BGE-M3。</p></section>
      <section className="parameter-section"><h3>3. 检索策略 (RETRIEVAL) · 参数预览</h3><div className="range-head"><label htmlFor="kbTopK">单次召回数量 (Top-K)</label><output>{parameterDraft.topK}</output></div><input id="kbTopK" max={50} min={1} onChange={(event) => setParameterDraft((current) => ({ ...current, topK: Number(event.target.value) }))} type="range" value={parameterDraft.topK} /><div className="range-head"><label htmlFor="kbScore">相似度阈值 (Score Threshold)</label><output>{parameterDraft.score.toFixed(2)}</output></div><input id="kbScore" max={1} min={0} onChange={(event) => setParameterDraft((current) => ({ ...current, score: Number(event.target.value) }))} step={0.01} type="range" value={parameterDraft.score} /><p className="parameter-hint">召回数量和阈值仅在页面中预览，不影响当前服务端检索配置。</p></section>
      <section className="parameter-section"><h3>4. 高级策略 (ADVANCED) · 参数预览</h3><div className="rerank-row"><label htmlFor="kbRerank">启用 Rerank 重排</label><label className="switch"><input aria-label="启用 Rerank 重排" checked={parameterDraft.rerank} id="kbRerank" onChange={(event) => setParameterDraft((current) => ({ ...current, rerank: event.target.checked }))} type="checkbox" /><span className="slider" /></label></div><select aria-label="Rerank 模型" className="field" defaultValue={parameterDraft.rerankModel} disabled><option value="BAAI/bge-reranker-large">BAAI/bge-reranker-large</option></select></section>
      <div className="math-preview"><strong>导入配置预览</strong><p>{chunkStrategies.find((item) => item.value === parameterDraft.strategy)?.label} · 大小 {parameterDraft.chunk} · 重叠 {parameterDraft.overlap}<br />模型 {parameterDraft.model}；检索参数仅作预览，不影响服务端配置。</p></div>
    </div><div className="drawer-foot"><button className="btn" onClick={() => setParametersOpen(false)} type="button">取消</button><button className="btn primary" onClick={() => void saveParameters()} type="button">保存并应用</button></div></aside> : null}
    {detailRow && (detailRow.entry?.store_id === storeId || detailRow.file?.store_id === storeId) ? <aside aria-label="知识详情" aria-modal="true" className="drawer detail-drawer open" role="dialog"><div className="drawer-head"><h2>知识详情</h2><button aria-label="关闭知识详情" autoFocus className="close" onClick={() => { detailRequestId.current += 1; setDetailRow(null); }} type="button">×</button></div><div className="drawer-body">
      <div className="detail-heading"><span className={`file-icon ${detailRow.type}`}>{knowledgeIconLabel(detailRow)}</span><strong>{detailRow.title}</strong><span className={`badge ${detailRow.review === "approved" ? "ok" : "wait"}`}>{detailApproval}</span></div>
      {detailRow.file ? detailLoading ? <LoadingState /> : versionDetail ? <>
        <div className="detail-meta"><div className="detail-meta-row"><span>所属分类</span><strong>{detailCategory}</strong></div><div className="detail-meta-row"><span>当前有效</span><strong>{fileDetail?.active_version_number ? `v${fileDetail.active_version_number}` : "暂无"}</strong></div><div className="detail-meta-row"><span>本版状态</span><strong>{documentStatusText(versionDetail.status)} · {versionDetail.chunk_count} 块</strong></div><div className="detail-meta-row"><span>分块策略</span><strong>{chunkStrategies.find((item) => item.value === versionDetail.config.strategy)?.label}</strong></div><div className="detail-meta-row"><span>分块参数</span><strong>{versionDetail.config.chunk_size} / 重叠 {versionDetail.config.overlap}</strong></div><div className="detail-meta-row"><span>适用范围</span><strong>{storeName}</strong></div></div>
        <label className="label kb-extra-field">查看版本<select aria-label="查看文件版本" className="field" onChange={(event) => void selectDocumentVersion(Number(event.target.value))} value={versionDetail.version_number}>{fileDetail?.versions.map((version) => <option key={version.id} value={version.version_number}>v{version.version_number} · {documentStatusText(version.status)}{version.is_active ? " · 当前有效" : ""}</option>)}</select></label>
        <div className="kb-detail-actions"><button className="btn" onClick={() => { setEditingFile(detailRow.file!); setFileCategoryDraft(detailRow.file?.category_id ?? ""); setDetailRow(null); }} type="button">编辑知识</button><button className="btn" onClick={() => void downloadOriginal()} type="button">下载原文件</button>{versionDetail.status.startsWith("failed") ? <button className="btn" disabled={reviewSubmitting} onClick={() => void retryFileVersion()} type="button">重试处理</button> : null}<button className="btn" onClick={() => { setPendingFileAction({ file: detailRow.file!, action: detailRow.file?.archived_at ? "restore" : "archive" }); setDetailRow(null); }} type="button">{detailRow.file?.archived_at ? "恢复" : "归档"}</button><button className="btn" onClick={() => { setPendingFileAction({ file: detailRow.file!, action: "delete" }); setDetailRow(null); }} type="button">删除</button></div>
        {versionDetail.status === "review_required" ? <div className="kb-review-warning" role="status">只要有关键内容无法可靠识别，整个新版本保持待复核，本版 0 向量；旧有效版本继续保留。请对照原文件确认每个问题单元。</div> : null}
        {versionDetail.error_code ? <p className="kb-file-error">处理错误码：{versionDetail.error_code}</p> : null}
        <section className="detail-section"><h3>解析单元</h3>{versionDetail.units.map((unit) => <div className="kb-review-unit" key={unit.unit_index}><strong>{unit.source_locator.page ? `第 ${unit.source_locator.page} 页` : unit.unit_kind === "image" ? "图片" : `单元 ${unit.unit_index + 1}`} · {unit.needs_review ? "待复核" : "已确认"}</strong>{unit.issue_codes.length ? <small>问题码：{unit.issue_codes.join("、")}</small> : null}<p>原始解析：{unit.raw_text || "未识别到文本，请下载原文件核对"}</p>{unit.needs_review && versionDetail.status === "review_required" ? <><label className="label">修订并确认<textarea aria-label={`修订单元 ${unit.unit_index + 1}`} className="field kb-review-text" onChange={(event) => setReviewDrafts((current) => ({ ...current, [unit.unit_index]: event.target.value }))} value={reviewDrafts[unit.unit_index] ?? ""} /></label><button className="btn primary" disabled={reviewSubmitting} onClick={() => void submitReview(unit.unit_index)} type="button">确认此单元</button></> : <p>清洗内容：{unit.cleaned_text}</p>}</div>)}</section>
        <div className="detail-note"><span className="detail-note-icon">ⓘ</span><div><strong>使用说明</strong><span>索引完成后，请在 Agent 的知识库配置中审批并绑定文档，再发布配置用于检索。回答仅供人工审核，不自动发送。</span></div></div>
      </> : <ErrorState message="文件详情加载失败" retry={() => void openKnowledgeRow(detailRow)} /> : <>
        <div className="detail-meta"><div className="detail-meta-row"><span>所属分类</span><strong>{detailCategory}</strong></div><div className="detail-meta-row"><span>当前版本</span><strong>v{detailRow.version}<small>{knowledgeDate(detailRow.updated)} 更新</small></strong></div><div className="detail-meta-row"><span>适用范围</span><strong>{storeName}</strong></div><div className="detail-meta-row"><span>语义类型</span><strong>{detailSemantic}</strong></div><div className="detail-meta-row"><span>文件来源</span><strong>{detailRow.entry?.source ?? "未记录"}</strong></div><div className="detail-meta-row"><span>创建人</span><strong>—</strong></div><div className="detail-meta-row"><span>最后更新</span><strong>{knowledgeDate(detailRow.updated)}</strong></div></div>
        <section className="detail-section detail-summary"><h3>内容摘要</h3><p>{detailRow.entry?.answer}</p></section>
        <div className="detail-note"><span className="detail-note-icon">ⓘ</span><div><strong>使用说明</strong><span>本知识仅用于 AI 建议生成与坐席人工复核，不支持公开自动回复。请结合实际订单情况与平台最新政策进行判断。</span></div></div>
        {detailRow.entry ? <div className="kb-detail-actions"><button className="btn" onClick={() => { setEditingEntry(detailRow.entry!); setDetailRow(null); setEntryEditorOpen(true); }} type="button">编辑知识</button>{detailRow.entry.status !== "published" ? <button className="btn primary" disabled={detailRow.entry.statement_type === "unknown"} onClick={() => { void publishEntry(detailRow.entry!); setDetailRow(null); }} type="button">审批并发布</button> : null}{detailRow.entry.vectorization_status === "failed" ? <button className="btn" onClick={() => { void retryVectorization(detailRow.entry!); setDetailRow(null); }} type="button">重试向量化</button> : null}{detailRow.entry.status !== "archived" ? <button className="btn" onClick={() => { void archiveEntry(detailRow.entry!); setDetailRow(null); }} type="button">归档</button> : null}<button className="btn" onClick={() => { void removeEntry(detailRow.entry!); setDetailRow(null); }} type="button">删除</button></div> : null}
      </>}
    </div></aside> : null}
    {categoryEditorOpen ? <div aria-label={editingCategory ? "编辑分类" : "新增知识分类"} aria-modal="true" className="modal category-modal open" role="dialog"><div className="modal-head"><h2>{editingCategory ? "编辑分类" : "新增知识分类"}</h2><button aria-label="关闭新增分类" autoFocus className="close" onClick={() => setCategoryEditorOpen(false)} type="button">×</button></div>{categoryForm}{categoryTree.length ? <div className="kb-category-manager"><strong>已有分类</strong>{categoryTree.map((category) => <div className="kb-category-manager-row" key={category.id}><span>{`${"— ".repeat(category.depth)}${category.name}`}</span><button aria-label={`编辑分类：${category.name}`} onClick={() => setEditingCategory(category)} type="button">编辑</button>{customCategories.some((item) => item.id === category.id) ? <button aria-label={`删除分类：${category.name}`} disabled={Boolean(deletingCategoryId)} onClick={() => requestCategoryDelete(category)} type="button">删除</button> : null}</div>)}</div> : null}</div> : null}
    {pendingCategoryDelete ? <div aria-label="删除自定义分类" aria-modal="true" aria-describedby="kb-delete-category-warning" className="modal category-modal open" role="dialog"><div className="modal-head"><h2>删除自定义分类</h2><button aria-label="关闭删除确认" className="close" disabled={Boolean(deletingCategoryId)} onClick={() => setPendingCategoryDelete(null)} type="button">×</button></div><div className="modal-content"><p className="kb-delete-category-copy">确定删除分类 <strong>{pendingCategoryDelete.name}</strong> 吗？</p><p className="kb-delete-category-warning" id="kb-delete-category-warning">仅空分类可以删除。分类下的知识或子分类需先移除；删除后无法恢复。</p></div><div className="modal-foot"><button autoFocus className="btn" disabled={Boolean(deletingCategoryId)} onClick={() => setPendingCategoryDelete(null)} type="button">取消</button><button className="btn danger" disabled={Boolean(deletingCategoryId)} onClick={() => void removeCategory()} type="button">{deletingCategoryId ? "正在删除…" : "删除分类"}</button></div></div> : null}
    {editingFile ? <div aria-label="编辑文件知识" aria-modal="true" className="modal category-modal open" role="dialog"><div className="modal-head"><h2>编辑知识</h2><button aria-label="关闭编辑文件" autoFocus className="close" onClick={() => setEditingFile(null)} type="button">×</button></div><div className="modal-content"><p>文件：<strong>{editingFile.filename}</strong></p><p className="parameter-hint">调整分类不改变已有文件版本；替换文件会创建新的不可变版本。归档文件须先恢复才能替换。</p><label className="label">归属分类<select aria-label="文件归属分类" className="field" onChange={(event) => setFileCategoryDraft(event.target.value)} value={fileCategoryDraft}><option value="">请选择分类</option>{categoryTree.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label></div><div className="modal-foot"><button className="btn" disabled={Boolean(editingFile.archived_at) || fileActionSubmitting} onClick={() => { setReplacementTarget(editingFile); setSelectedUploadCategoryId(editingFile.category_id ?? ""); setSelectedFile(null); setUploadKind("document"); setAddMode("upload"); setEditingFile(null); setEntryEditorOpen(true); }} type="button">替换文件</button><button className="btn" onClick={() => setEditingFile(null)} type="button">取消</button><button className="btn primary" disabled={!fileCategoryDraft || fileActionSubmitting} onClick={() => void saveFileCategory()} type="button">{fileActionSubmitting ? "正在保存…" : "保存分类"}</button></div></div> : null}
    {pendingFileAction ? <div aria-label="文件操作确认" aria-modal="true" className="modal category-modal open" role="dialog"><div className="modal-head"><h2>{pendingFileAction.action === "archive" ? "归档文件" : pendingFileAction.action === "restore" ? "恢复文件" : "删除文件"}</h2><button aria-label="关闭文件操作确认" className="close" disabled={fileActionSubmitting} onClick={() => setPendingFileAction(null)} type="button">×</button></div><div className="modal-content"><p>确认{pendingFileAction.action === "archive" ? "归档" : pendingFileAction.action === "restore" ? "恢复" : "删除"} <strong>{pendingFileAction.file.filename}</strong>？</p><p className="parameter-hint">{pendingFileAction.action === "delete" ? "这会将文件从当前店铺列表隐藏；原文件、版本和审计记录保留。" : pendingFileAction.action === "archive" ? "归档后文件仍可查看，但不会参与后续索引认领；可再次恢复。" : "恢复后文件重新成为当前店铺可用资料。"}</p></div><div className="modal-foot"><button className="btn" disabled={fileActionSubmitting} onClick={() => setPendingFileAction(null)} type="button">取消</button><button className={`btn ${pendingFileAction.action === "delete" ? "danger" : "primary"}`} disabled={fileActionSubmitting} onClick={() => void applyFileAction()} type="button">{fileActionSubmitting ? "正在处理…" : "确认"}</button></div></div> : null}
    {entryEditorOpen ? <div aria-label={editingEntry ? "编辑知识" : replacementTarget ? "替换知识文档" : "新增知识文档"} aria-modal="true" className="modal open" role="dialog"><div className="modal-head"><h2>{editingEntry ? "编辑知识" : replacementTarget ? "替换知识文档" : addMode === "manual" ? "手动录入知识" : "新增知识文档"}</h2><button aria-label="关闭新增知识" autoFocus className="close" onClick={() => { setEntryEditorOpen(false); setReplacementTarget(null); }} type="button">×</button></div>
      {editingEntry ? entryForm : <><div aria-label="新增知识方式" className="mode-tabs" role="tablist"><button aria-selected={addMode === "upload"} className={`mode-tab${addMode === "upload" ? " active" : ""}`} onClick={() => setAddMode("upload")} role="tab" type="button">上传文档</button><button aria-selected={addMode === "manual"} className={`mode-tab${addMode === "manual" ? " active" : ""}`} onClick={() => setAddMode("manual")} role="tab" type="button">手动录入</button></div>
        {addMode === "manual" ? <form className="kb-modal-form" onSubmit={addEntry}><div className="modal-content manual-fields"><label className="label">知识标题<input className="field" maxLength={120} name="question" placeholder="输入知识标题" required /></label><label className="label">知识内容<textarea className="field" maxLength={10000} name="answer" placeholder="输入供内部审核的知识正文" required rows={7} /></label><p className="parameter-hint">保存为当前店铺草稿；知识语义类型须在审批前补齐。</p><input defaultValue="unknown" name="statement_type" type="hidden" /><input defaultValue="none" name="customer_scope" type="hidden" /><input defaultValue="" name="tags" type="hidden" /><div className="form-row"><label className="label">归属分类<select className="field select" defaultValue={selectedCategoryId} name="category_id" required><option value="">请选择分类</option>{categoryTree.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label></div></div><div className="modal-foot"><button className="btn" onClick={() => setEntryEditorOpen(false)} type="button">取消</button><button className="btn primary" disabled={entrySubmitting} type="submit">保存知识</button></div></form> : <><div className="modal-content"><div aria-label="选择或拖入知识文件" className="upload" onClick={() => fileInputRef.current?.click()} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); chooseFile(event.dataTransfer.files[0]); }} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); fileInputRef.current?.click(); } }} role="button" tabIndex={0}><div className="upload-icon">☁</div><strong>{selectedFile ? `已选择：${selectedFile.name}` : "点击或拖拽文件到此处上传"}</strong><small>{selectedFile ? `${(selectedFile.size / 1024).toFixed(1)} KB · 上传后由服务端解析并保存状态` : "支持 PDF、Word、图片、Markdown、Excel、CSV、TXT（最大 20 MiB）"}</small></div>
          {selectedFile && !replacementTarget && ["csv", "xlsx"].includes(selectedFile.name.split(".").pop()?.toLowerCase() ?? "") ? <label className="label kb-extra-field">导入方式<select aria-label="表格导入方式" className="field" onChange={(event) => setUploadKind(event.target.value as "document" | "faq")} value={uploadKind}><option value="document">通用文档 → MinerU / 清洗 / 分块 / 向量</option><option value="faq">旧版 FAQ 表格导入</option></select></label> : null}
          {uploadKind === "document" ? <><div className="form-row"><label className="label">归属分类<select className="field select" disabled={Boolean(replacementTarget)} onChange={(event) => setSelectedUploadCategoryId(event.target.value)} value={selectedUploadCategoryId}><option value="">请选择分类</option>{categoryTree.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label><label className="label">分段策略 (Chunking)<select aria-label="上传分段策略" className="field select" onChange={(event) => setSegmentMode(event.target.value as DocumentStrategy)} value={segmentMode}>{chunkStrategies.map((item) => <option disabled={selectedFile ? !strategySupportsFile(item.value, selectedFile.name) : false} key={item.value} value={item.value}>{item.label}</option>)}</select></label></div><label className="label kb-extra-field">解析档位<select aria-label="上传解析档位" className="field" onChange={(event) => setParserMode(event.target.value as DocumentIndexConfig["parser_mode"])} value={parserMode}><option value="auto">自动：文本优先，必要时 OCR</option><option value="flash">Flash：常规文本解析</option><option value="basic">Basic OCR：仅 PDF/图片</option></select></label><div className="kb-config-snapshot">本文件将使用：{chunkStrategies.find((item) => item.value === segmentMode)?.label} · 大小 {parameters.chunk} · 重叠 {segmentMode === "table_rows" ? 0 : parameters.overlap} · {parameters.model}。上传后配置冻结；有关键内容不可靠时整版待复核、0 新向量。</div></> : <p className="parameter-hint kb-extra-field">FAQ CSV/XLSX 使用现有导入队列，分类取文件中的 category_code；不使用当前通用文档分块配置。</p>}
        </div><div className="modal-foot"><button className="btn" onClick={() => { setEntryEditorOpen(false); setReplacementTarget(null); }} type="button">取消</button><button className="btn primary" disabled={!selectedFile || uploadSubmitting} onClick={() => void submitSelectedFile()} type="button">{uploadSubmitting ? "正在提交…" : "确认上传并解析"}</button></div></>}
      </>}
    </div> : null}
    {pendingReplacement ? <div aria-label="替换同名文件" aria-modal="true" className="modal category-modal open" role="dialog"><div className="modal-head"><h2>替换同名文件</h2><button aria-label="关闭替换确认" className="close" onClick={() => { setPendingReplacement(null); setEntryEditorOpen(true); }} type="button">×</button></div><div className="modal-content"><p>当前店铺已有 <strong>{pendingReplacement.filename}</strong>。内容或配置有变化时会创建新版本；完全相同则复用已有版本。旧有效版本在新版本全部完成前继续保留。文件沿用现有分类。</p><p className="kb-review-warning">如果新版本有关键内容无法可靠识别，整版停在待复核，0 新向量。</p></div><div className="modal-foot"><button className="btn" onClick={() => { setPendingReplacement(null); setEntryEditorOpen(true); }} type="button">取消</button><button className="btn primary" disabled={uploadSubmitting} onClick={() => void performDocumentUpload(pendingReplacement.id)} type="button">{uploadSubmitting ? "正在提交…" : "替换旧文件"}</button></div></div> : null}
    {notice ? <div aria-live="polite" className="toast show" role="status">{notice}</div> : null}
  </div></AppShell>;
}
