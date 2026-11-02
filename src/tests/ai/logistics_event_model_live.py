"""Opt-in logistics COMPONENT acceptance: real DeepSeek/BGE/PG, simulated platform facts, zero send.

Run from src/backend with memory-only environment supplied by the controller.
No imports with database/model side effects happen before the CLI safety guards.
This does not test authenticated HTTP, UI, live platform reads or buyer delivery.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import inspect
import json
import logging
import os
import re
import sys
import time
import uuid
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import urlsplit

ARTIFACT_ROOT = Path(__file__).resolve().parents[1] / ".artifacts/agent-automation-20261102"
DATABASE_NAMES = {"crm_test", "crm_logistics_acceptance", "crm_agent_automation_acceptance"}
REQUIRED_TOOLS = {"query_order", "query_logistics", "search_knowledge", "notify_logistics_update"}
CRITERION_VERSION = "logistics-component-owned-evidence-v2"
KNOWLEDGE = (
    "Cedar Hub is a transit sorting checkpoint. "
    "Arrival at Cedar Hub means the parcel remains in transit, not delivered. "
    "雪松分拣中心是运输中的分拣节点。到达雪松分拣中心表示包裹仍在运输中，并非已送达。"
)
KNOWLEDGE_CONTEXT = (
    "For a parcel whose latest update is arrival at Cedar Hub, the current scan records sorting in transit. "
    "A hub scan is not proof of delivery and does not establish an arrival estimate. "
    "对于最新物流节点为到达雪松分拣中心的包裹，当前节点记录运输中分拣；中转扫描不是签收或预计送达日期。"
)
UNSAFE_FLAGS = (
    "real_tiktok_read_enabled",
    "real_tiktok_webhook_enabled",
    "real_tiktok_message_write_enabled",
    "real_tiktok_high_risk_write_enabled",
    "real_tiktok_automation_enabled",
    "auto_reply_enabled",
    "real_tiktok_logistics_notifications_enabled",
    "ai_marketing_enabled",
    "allow_mock_platform_adapters",
    "logistics_notifications_enabled",
)


class Blocked(RuntimeError):
    """Only a runner-owned stable reason; never include provider responses or environment values."""


def validate_database_environment(environment: dict[str, str]) -> str:
    target = environment.get("TEST_DATABASE_URL", "")

    def check(value: str) -> None:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "postgresql+asyncpg"
            or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.path.removeprefix("/") not in DATABASE_NAMES
            or parsed.query
            or parsed.fragment
        ):
            raise Blocked("isolated_loopback_test_database_required")

    check(target)
    configured = environment.get("DATABASE_URL")
    if configured:
        check(configured)
        if configured != target:
            raise Blocked("database_alias_must_match_test_database")
    return target


def validate_output(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(ARTIFACT_ROOT.resolve()) or resolved.suffix != ".json" or resolved.exists():
        raise Blocked("new_json_under_owned_artifacts_required")
    return resolved


def validate_runtime(settings: Any) -> None:
    if settings.app_env not in {"test", "integration"} or any(getattr(settings, key) for key in UNSAFE_FLAGS):
        raise Blocked("isolated_runtime_with_all_platform_capabilities_off_required")
    if not (
        settings.llm_enabled
        and settings.llm_primary_provider == "deepseek"
        and settings.llm_primary_model
        and settings.embedding_enabled
        and settings.embedding_provider == "local_bge"
        and settings.embedding_model == "BAAI/bge-m3"
        and settings.embedding_dimensions == 1024
    ):
        raise Blocked("real_deepseek_and_bge_required")


def validate_case(
    *,
    language: str,
    body: str,
    events: Any,
    citations: Any,
    evidence: dict[str, object],
    frozen_chunks: dict[str, str],
    retrieved_hits: list[Any],
    store_id: Any,
    file_id: Any,
    document_version: int,
    review_status: str,
) -> dict[str, object]:
    successful = {item.name for item in events if item.status in {"succeeded", "retrieved", "proposed"}}
    if not REQUIRED_TOOLS <= successful or review_status != "approved":
        raise Blocked("required_native_tools_and_owned_file_evidence_missing")
    if (
        len(frozen_chunks) != 2
        or set(frozen_chunks.values()) != {KNOWLEDGE, KNOWLEDGE_CONTEXT}
        or not citations
        or any(citation not in frozen_chunks for citation in citations)
    ):
        raise Blocked("nonempty_frozen_related_chunk_citations_required")
    citation_evidence = []
    for citation in citations:
        text = frozen_chunks[citation]
        retrieved = any(
            str(hit.chunk_id) == citation
            and hit.document_id == file_id
            and hit.document_version == document_version
            and hit.safety_metadata.store_id == store_id
            and hit.content == text
            for hit in retrieved_hits
        )
        if evidence.get(citation) != text or not retrieved:
            raise Blocked("citation_frozen_text_or_actual_retrieval_mismatch")
        citation_evidence.append(
            {
                "chunk_ref_sha256": hashlib.sha256(citation.encode()).hexdigest(),
                "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "scope_version_matched": True,
                "actually_retrieved": True,
            }
        )
    if not body.strip() or len(body) > 500 or "OLD-HISTORY-DO-NOT-REPORT" in body:
        raise Blocked("latest_node_only_concise_body_required")
    chinese = bool(re.search(r"[\u3400-\u9fff]", body))
    if (language == "en" and (chinese or "cedar" not in body.casefold())) or (
        language == "zh" and (not chinese or "雪松" not in body)
    ):
        raise Blocked("buyer_language_and_latest_node_required")
    return {"owned_file_fact_seen": True, "citation_evidence": citation_evidence}


def classify(error: Exception) -> str:
    if isinstance(error, Blocked):
        return str(error)
    if isinstance(error, TimeoutError):
        return "component_timeout"
    if type(error).__name__ in {"LLMProviderError", "EmbeddingProviderError", "RerankingProviderError"}:
        return "real_provider_or_retrieval_failed"
    if isinstance(error, ValueError) and str(error) in {
        "notification_required_tool_missing",
        "notification_generation_invalid",
        "notification_agent_changed",
    }:
        return str(error)
    return "component_execution_failed"


def case_progress(model: Any, *, phase: str, elapsed: float, error: Exception) -> dict[str, Any]:
    """失败也保留实际工具与用量；只投影固定名称/状态，不复制异常正文、参数和引用 ID。"""
    statuses = {
        "succeeded",
        "retrieved",
        "proposed",
        "no_hits",
        "no_knowledge_bound",
        "failed",
        "permission_denied",
        "missing_prerequisites",
        "missing_required_tools",
        "prerequisites_missing",
        "blocked",
        "proposal_already_submitted",
        "invalid_arguments",
        "tool_error",
        "tool_failed",
        "tool_unavailable",
        "cancelled",
        "timeout",
        "tool_result_too_large",
        "error",
    }
    citations = model.citations or getattr(model.toolset, "citations", ())
    return {
        "status": "failed",
        "phase": phase,
        "reason": classify(error),
        "tool_calls": [
            {
                "name": item.name if item.name in REQUIRED_TOOLS else "unavailable",
                "status": item.status if item.status in statuses else "unavailable",
            }
            for item in model.tool_events
        ],
        "input_tokens": model.input_tokens,
        "output_tokens": model.output_tokens,
        "citation_count": len(citations),
        "duration_seconds": round(elapsed, 3),
    }


async def embed_fixture(service: Any, expected_model: str) -> Any:
    embedding = await service.embed([KNOWLEDGE, KNOWLEDGE_CONTEXT])
    if (
        embedding.provider != "local_bge"
        or embedding.model != expected_model
        or len(embedding.vectors) != 2
        or any(len(vector) != 1024 for vector in embedding.vectors)
    ):
        raise Blocked("real_two_chunk_fixture_embedding_required")
    return embedding


async def seed(sessions: Any, settings: Any, ids: dict[str, uuid.UUID]) -> Any:
    from sqlalchemy import insert, select

    from app.agents.core.factory import build_embedding_service
    from app.agents.management.config_models import AgentConfig
    from app.agents.management.models import AgentConfigVersion
    from app.agents.management.repository import get_published_agent
    from app.agents.management.templates.schemas import TemplateConfig
    from app.agents.prompts.compiler import compile_prompt
    from app.knowledge_base.document_models import KnowledgeFile, KnowledgeFileChunk, KnowledgeFileVersion
    from app.shared.database.base import Role, User, user_roles
    from app.stores.models import Store

    now = datetime.now(UTC)
    async with sessions() as session:
        dataset = Path(__file__).with_name("datasets") / "five_agent_templates.json"
        source = dataset.read_bytes()
        templates = [item for item in json.loads(source) if item["code"] == "logistics_update_v1"]
        if len(templates) != 1:
            raise Blocked("frozen_logistics_template_missing")
        # 冻结七段与工具语义不变；fixture 的模型选择使用本轮真实配置，避免调用旧默认别名。
        config = TemplateConfig.model_validate(
            {
                **templates[0]["config"],
                "model_provider": settings.llm_primary_provider,
                "model_name": settings.llm_primary_model,
            }
        )
        if set(config.tool_names) != REQUIRED_TOOLS:
            raise Blocked("published_template_tools_mismatch")
        compiled = compile_prompt(config.prompt_sections)
        role = await session.scalar(select(Role).where(Role.code == "admin"))
        if role is None:
            raise Blocked("existing_admin_role_required")
        session.add_all(
            [
                Store(id=ids["store"], name="Synthetic logistics component", code=f"log-live-{ids['store'].hex}"),
                User(
                    id=ids["user"],
                    name="Synthetic component actor",
                    password_hash="not-a-login-password",
                    email=f"log-live-{ids['user'].hex}@example.test",
                ),
            ]
        )
        await session.flush()
        await session.execute(insert(user_roles).values(user_id=ids["user"], role_id=role.id, store_id=ids["store"]))
        session.add_all(
            [
                KnowledgeFile(
                    id=ids["file"],
                    store_id=ids["store"],
                    original_filename="synthetic-logistics.txt",
                    filename_key="synthetic-logistics.txt",
                    active_version_number=1,
                ),
                AgentConfig(
                    id=ids["agent"],
                    store_id=ids["store"],
                    name=config.default_agent_name,
                    code=f"log-live-{ids['agent'].hex}",
                    status="enabled",
                    published_version=1,
                    enabled_tools=list(config.tool_names),
                    created_by=ids["user"],
                    knowledge_scope={"mode": "bound_files_only", "file_ids": [str(ids["file"])]},
                ),
            ]
        )
        await session.flush()
        session.add(
            KnowledgeFileVersion(
                id=ids["version"],
                store_id=ids["store"],
                file_id=ids["file"],
                version_number=1,
                source_object_key=f"synthetic-component/{ids['file']}.txt",
                file_sha256=hashlib.sha256((KNOWLEDGE + "\n\n" + KNOWLEDGE_CONTEXT).encode()).hexdigest(),
                media_type="text/plain",
                config_json={"fixture": "declared_preparsed_chunk"},
                status="ready",
                created_by=ids["user"],
                publication_approval="approved_for_internal_review",
                statement_type="policy",
                customer_scope="generic",
                approved_by=ids["user"],
                approved_at=now,
                completed_at=now,
            )
        )
        await session.flush()
        # 实际 BGE 生成入库向量；本组件只跳过文件导入/解析 API，不替换查询或重排。
        embedding = await embed_fixture(build_embedding_service(settings), settings.embedding_model)
        for index, text in enumerate((KNOWLEDGE, KNOWLEDGE_CONTEXT)):
            session.add(
                KnowledgeFileChunk(
                    id=ids["chunk"] if index == 0 else ids["context_chunk"],
                    store_id=ids["store"],
                    file_id=ids["file"],
                    version_id=ids["version"],
                    unit_index=0,
                    chunk_index=index,
                    content=text,
                    token_count=120,
                    content_hash=hashlib.sha256(text.encode()).hexdigest(),
                    strategy="declared_component_fixture",
                    heading_path=[],
                    source_locator={"fixture": True},
                    parser_version="component-fixture-v1",
                    cleaning_version="clean-v1",
                    embedding_model=embedding.model,
                    embedding_revision="live-service",
                    embedding=embedding.vectors[index],
                )
            )
        session.add(
            AgentConfigVersion(
                store_id=ids["store"],
                agent_config_id=ids["agent"],
                version=1,
                name=config.default_agent_name,
                code=f"log-live-{ids['agent'].hex}",
                agent_type=config.agent_type,
                model_provider=config.model_provider,
                model_name=config.model_name,
                prompt_sections=dict(compiled.sections),
                prompt_hash=compiled.content_sha256,
                tool_names=list(config.tool_names),
                file_ids=[str(ids["file"])],
                ready_for_v2=True,
                published_by=ids["user"],
                template_source_json={
                    "fixture_source": "five_agent_templates.json",
                    "dataset_sha256": hashlib.sha256(source).hexdigest(),
                },
            )
        )
        await session.commit()
        agent = await get_published_agent(session, store_id=ids["store"], config_id=ids["agent"])
        if agent is None:
            raise Blocked("synthetic_publication_missing")
        return agent


async def run_language(
    sessions: Any, settings: Any, ids: dict[str, uuid.UUID], agent: Any, language: str, case_report: dict[str, Any]
) -> dict[str, Any]:
    from sqlalchemy import func, select

    from app.agents.automation.models import AutomationDelivery
    from app.agents.rag.search import RagRetrievalService
    from app.agents.tools.logistics_updates import event_agent
    from app.agents.tools.logistics_updates.contracts import (
        BoundLogisticsEvent,
        LogisticsObservation,
        LogisticsScope,
        TrackingEvent,
    )
    from app.agents.tools.logistics_updates.integration import NativeNotificationModel, VerifiedLogisticsSource
    from app.agents.tools.logistics_updates.models import LogisticsNotification, LogisticsNotificationPolicy
    from app.conversations.models import Conversation, Message
    from app.customers.models import Customer
    from app.integrations.adapters import PlatformAdapter, TikTokAdapter
    from app.integrations.tiktok_read import TikTokOrder, TikTokPayment
    from app.integrations.tiktok_write import TikTokMessageClient
    from app.orders.models import Order

    started = time.monotonic()
    customer, conversation, order = (uuid.uuid4() for _ in range(3))
    now = datetime.now(UTC).replace(microsecond=0)
    buyer = "Where is my parcel now?" if language == "en" else "我的包裹现在到哪里了？"
    latest = TrackingEvent(
        occurred_at=now - timedelta(minutes=5),
        status="in_transit",
        description="Arrived at Cedar Hub" if language == "en" else "已到达雪松分拣中心",
    )
    scope = LogisticsScope(
        store_id=ids["store"],
        customer_id=customer,
        conversation_id=conversation,
        order_id=order,
        package_id=f"synthetic-{language}",
    )
    context = BoundLogisticsEvent(scope=scope, event=latest, buyer_language=language)
    async with sessions() as session:
        session.add(
            Customer(id=customer, store_id=ids["store"], platform="tiktok", external_customer_id=str(customer.int))
        )
        await session.flush()
        session.add_all(
            [
                Conversation(
                    id=conversation,
                    store_id=ids["store"],
                    customer_id=customer,
                    platform="tiktok",
                    external_conversation_id=str(conversation.int),
                    status="active",
                ),
                Order(
                    id=order,
                    store_id=ids["store"],
                    customer_id=customer,
                    platform="tiktok",
                    external_order_id=str(order.int),
                    status="IN_TRANSIT",
                    currency="USD",
                    total_amount=12,
                ),
            ]
        )
        await session.flush()
        session.add(
            Message(
                store_id=ids["store"],
                conversation_id=conversation,
                customer_id=customer,
                direction="inbound",
                platform="tiktok",
                external_message_id=f"synthetic-{uuid.uuid4().hex}",
                status="received",
                role="user",
                message_type="text",
                content=buyer,
                language=language,
            )
        )
        if language == "en":
            session.add(
                LogisticsNotificationPolicy(
                    store_id=ids["store"],
                    agent_id=ids["agent"],
                    authorized_by=ids["user"],
                    enabled=True,
                    mode="preview",
                    enabled_at=now - timedelta(hours=1),
                    revision=1,
                )
            )
        await session.commit()

    remote = TikTokOrder(
        id=str(order.int),
        status="IN_TRANSIT",
        create_time=int((now - timedelta(days=1)).timestamp()),
        payment=TikTokPayment(currency="USD", total_amount="12.00"),
    )

    async def simulated_order(session: Any, actor: Any, conversation_id: Any, external_order_id: Any) -> Any:
        if actor.id != ids["user"] or conversation_id != conversation or external_order_id != str(order.int):
            raise Blocked("simulated_order_scope_mismatch")
        return None, None, remote

    async def simulated_observations(
        session: Any, actor: Any, store_id: Any, conversation_id: Any, order_id: Any, cutoff: Any
    ) -> Any:
        if (actor.id, store_id, conversation_id, order_id) != (ids["user"], ids["store"], conversation, order):
            raise Blocked("simulated_logistics_scope_mismatch")
        old = TrackingEvent(
            occurred_at=now - timedelta(hours=1), status="shipped", description="OLD-HISTORY-DO-NOT-REPORT"
        )
        return VerifiedLogisticsSource(
            (LogisticsObservation(scope=scope, buyer_language=language, events=(old, latest)),), buyer
        )

    send_calls = 0

    async def deny_send(*args: Any, **kwargs: Any) -> Any:
        nonlocal send_calls
        send_calls += 1
        raise Blocked("component_must_not_send")

    rag_results = []
    original_retrieve = RagRetrievalService.retrieve

    async def observe_retrieve(self: Any, *args: Any, **kwargs: Any) -> Any:
        result = await original_retrieve(self, *args, **kwargs)
        rag_results.append(result)
        return result

    # 仅注入经批准的模拟平台事实；其余授权、文件检索、模型和复核全部走产品实现。
    with ExitStack() as stack:
        stack.enter_context(patch.object(event_agent, "_verified_sidebar_order", simulated_order))
        stack.enter_context(
            patch("app.agents.tools.logistics_updates.integration.read_verified_observations", simulated_observations)
        )
        stack.enter_context(patch.object(RagRetrievalService, "retrieve", observe_retrieve))
        for cls, method in (
            (PlatformAdapter, "send_message"),
            (TikTokAdapter, "send_message"),
            (TikTokMessageClient, "send_text_message"),
        ):
            stack.enter_context(patch.object(cls, method, deny_send))
        model = NativeNotificationModel(
            settings, agent, buyer, sessions=sessions, actor_id=ids["user"], delivery_mode="preview"
        )
        try:
            case_report["phase"] = "generate"
            candidate = await model.generate(context)
            case_report["phase"] = "independent_review"
            decision = await model.review(context, candidate)
            case_report["review"] = decision.status
            if decision.status != "approved" or not decision.text:
                raise Blocked("independent_review_not_approved")
            case_report["phase"] = "validate_evidence"
            evidence = model.toolset.evidence if model.toolset is not None else {}
            citation_validation = validate_case(
                language=language,
                body=decision.text,
                events=model.tool_events,
                citations=model.citations,
                evidence=evidence,
                frozen_chunks={str(ids["chunk"]): KNOWLEDGE, str(ids["context_chunk"]): KNOWLEDGE_CONTEXT},
                retrieved_hits=[hit for result in rag_results for hit in result.hits],
                store_id=ids["store"],
                file_id=ids["file"],
                document_version=1,
                review_status=decision.status,
            )
            if not rag_results or any(
                result.embedding_provider != "local_bge"
                or not result.reranker_model
                or not result.hits
                or result.candidate_count <= 1
                for result in rag_results
            ):
                raise Blocked("real_bge_retrieval_and_reranking_required")
            case_report["phase"] = "assert_zero_delivery"
            async with sessions() as session:
                outbound = await session.scalar(
                    select(func.count())
                    .select_from(Message)
                    .where(Message.store_id == ids["store"], Message.direction == "outbound")
                )
                notifications = await session.scalar(
                    select(func.count())
                    .select_from(LogisticsNotification)
                    .where(LogisticsNotification.store_id == ids["store"])
                )
                deliveries = await session.scalar(
                    select(func.count())
                    .select_from(AutomationDelivery)
                    .where(AutomationDelivery.store_id == ids["store"])
                )
            if send_calls or outbound or notifications or deliveries:
                raise Blocked("component_created_delivery_side_effect")
            return {
                "language": language,
                "status": "passed",
                "phase": "completed",
                "scope": "isolated_component",
                "platform_facts": "simulated_verified_fixture",
                "model_provider": agent.model_provider,
                "model": agent.model_name,
                "synthetic_body": decision.text,
                "review": "approved",
                "tool_calls": [{"name": item.name, "status": item.status} for item in model.tool_events],
                "citation_count": len(model.citations),
                "owned_file_fact_seen": True,
                "citation_evidence": citation_validation["citation_evidence"],
                "rag_query_count": len(rag_results),
                "rag_candidate_counts": [result.candidate_count for result in rag_results],
                "embedding_provider": rag_results[0].embedding_provider,
                "embedding_model": rag_results[0].embedding_model,
                "reranker_model": rag_results[0].reranker_model,
                "input_tokens": model.input_tokens,
                "output_tokens": model.output_tokens,
                "send_calls": send_calls,
                "outbound_rows": outbound,
                "notification_rows": notifications,
                "automation_delivery_rows": deliveries,
                "duration_seconds": round(time.monotonic() - started, 3),
            }
        except Exception as error:
            case_report.update(
                case_progress(model, phase=case_report["phase"], elapsed=time.monotonic() - started, error=error)
            )
            case_report["rag_query_count"] = len(rag_results)
            case_report["send_calls"] = send_calls
            case_report["rag_candidate_counts"] = [result.candidate_count for result in rag_results]
            raise


async def execute(settings: Any, report: dict[str, Any]) -> None:
    # 配置依赖注入使用真实 Settings，禁止读取本机 .env；不能改变 RBAC 或审批判断。
    with patch("app.shared.config.settings.get_settings", lambda: settings):
        from sqlalchemy import delete, select

        import app.shared.database.models  # noqa: F401
        from app.agents.management.config_models import AgentConfig
        from app.agents.tools.logistics_updates.models import LogisticsNotificationPolicy
        from app.conversations.models import Conversation, Message
        from app.customers.models import Customer
        from app.knowledge_base.document_models import KnowledgeFile
        from app.orders.models import Order
        from app.shared.database.base import User
        from app.shared.database.session import engine, session_factory
        from app.stores.models import Store

        ids = {name: uuid.uuid4() for name in ("store", "user", "file", "version", "chunk", "context_chunk", "agent")}
        try:
            report["frozen_knowledge"] = {
                "store_ref_sha256": hashlib.sha256(str(ids["store"]).encode()).hexdigest(),
                "file_ref_sha256": hashlib.sha256(str(ids["file"]).encode()).hexdigest(),
                "document_version": 1,
                "chunks": [
                    {
                        "chunk_ref_sha256": hashlib.sha256(str(ids[key]).encode()).hexdigest(),
                        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                    }
                    for key, text in (("chunk", KNOWLEDGE), ("context_chunk", KNOWLEDGE_CONTEXT))
                ],
            }
            report["phase"] = "seed_declared_fixture"
            report["template_fixture_sha256"] = hashlib.sha256(
                (Path(__file__).with_name("datasets") / "five_agent_templates.json").read_bytes()
            ).hexdigest()
            agent = await seed(session_factory, settings, ids)
            report["prompt_sha256"] = agent.prompt_hash
            for language in ("en", "zh"):
                report["phase"] = f"generate_review_{language}"
                case = {
                    "language": language,
                    "status": "failed",
                    "scope": "isolated_component",
                    "model_provider": agent.model_provider,
                    "model": agent.model_name,
                    "phase": "case_fixture",
                    "tool_calls": [],
                    "citation_count": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                }
                report["cases"].append(case)
                case.update(await run_language(session_factory, settings, ids, agent, language, case))
            report["status"] = "passed"
        except Exception as error:
            report["status"], report["reason"] = "failed", classify(error)
            if report["cases"] and report["cases"][-1]["status"] == "failed":
                report["cases"][-1].setdefault("reason", classify(error))
        finally:
            try:
                async with session_factory() as session:
                    # 随机 Store ID 与自有 code 双重限定；只清理本次 fixture，审计记录保留其历史引用。
                    owned = await session.scalar(
                        select(Store.id).where(Store.id == ids["store"], Store.code == f"log-live-{ids['store'].hex}")
                    )
                    if owned is not None:
                        for model in (
                            LogisticsNotificationPolicy,
                            Message,
                            Conversation,
                            Order,
                            Customer,
                            AgentConfig,
                            KnowledgeFile,
                        ):
                            await session.execute(delete(model).where(model.store_id == ids["store"]))
                    await session.execute(
                        delete(Store).where(Store.id == ids["store"], Store.code == f"log-live-{ids['store'].hex}")
                    )
                    await session.execute(
                        delete(User).where(
                            User.id == ids["user"], User.email == f"log-live-{ids['user'].hex}@example.test"
                        )
                    )
                    await session.commit()
                    remaining = await session.scalar(select(Store.id).where(Store.id == ids["store"]))
                    actor_remaining = await session.scalar(select(User.id).where(User.id == ids["user"]))
                    if remaining or actor_remaining:
                        raise Blocked("owned_fixture_cleanup_incomplete")
                report["cleanup"] = "owned_fixture_removed_audit_retained"
            except Exception:
                report.update(status="failed", reason="owned_fixture_cleanup_failed", cleanup="failed")
            finally:
                await engine.dispose()


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enable-live", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(arguments)
    if not args.enable_live:
        print("explicit_live_opt_in_required", file=sys.stderr)
        return 2
    try:
        target = validate_database_environment(dict(os.environ))
        output = validate_output(args.output)
        if os.environ.get("APP_ENV") not in {"test", "integration"}:
            raise Blocked("isolated_test_or_integration_environment_required")
        os.environ["DATABASE_URL"] = target
        logging.disable(logging.CRITICAL)
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
        from app.shared.config.settings import Settings

        settings = Settings(_env_file=None)
        validate_runtime(settings)
    except Exception as error:
        print(classify(error), file=sys.stderr)
        return 2
    report: dict[str, Any] = {
        "schema_version": 1,
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "criterion_version": CRITERION_VERSION,
        "criterion_sha256": hashlib.sha256(inspect.getsource(validate_case).encode()).hexdigest(),
        "scope": "isolated_component",
        "status": "failed",
        "cases": [],
        "platform_facts": "simulated_verified_fixture",
        "provider_mode": "configured_real_provider",
        "fixture_ingestion": "declared_chunk_with_real_embedding_not_file_import_api",
        "http_auth_ui_acceptance": False,
        "live_platform_read": False,
        "buyer_delivery": False,
    }
    try:
        asyncio.run(execute(settings, report))
    except Exception as error:
        report.update(status="failed", reason=classify(error))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    print(json.dumps({"scope": "isolated_component", "status": report["status"], "case_count": len(report["cases"])}))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
