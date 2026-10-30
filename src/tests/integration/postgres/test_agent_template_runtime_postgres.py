"""批次发布配置通过真实运行、授权工具和文件检索进入人工复核。"""

import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from agent._review_helpers import accepted_review_turn
from sqlalchemy import delete, func, select
from test_agent_rag_postgres import approved_chunk_metadata, approved_document_fields, vector
from test_agent_template_application_postgres import env as env_fixture
from test_agent_template_batches import confirm, worker

from app.agents.management.config_models import AgentConfig
from app.agents.management.models import AgentConfigVersion
from app.agents.management.repository import list_enabled_agents
from app.agents.management.templates import preview, service
from app.agents.management.templates.lifecycle_schemas import TemplateUpdate
from app.agents.management.templates.models import AgentTemplate
from app.agents.management.templates.schemas import ApplicationPreviewRequest, KnowledgeSlot
from app.agents.prompts.sections import SECTION_TITLES
from app.agents.providers.tool_calling import FunctionCall, ToolTurn
from app.agents.rag import factory
from app.agents.rag.embeddings import EmbeddingResult
from app.agents.rag.retriever import retrieve_bound_files
from app.agents.runtime import execution
from app.agents.runtime.models import AgentRun
from app.agents.runtime.snapshot import freeze_debug_context, freeze_run_context
from app.agents.tools.access import current_permissions
from app.audit.models import AuditLog
from app.conversations.models import Conversation, Message
from app.customers.models import Customer
from app.knowledge_base.document_models import KnowledgeFile, KnowledgeFileChunk, KnowledgeFileVersion
from app.knowledge_base.models import KnowledgeChunk, KnowledgeDocument
from app.shared.config.settings import Settings
from app.shared.database.base import User
from app.tools.models import ToolCall

env = env_fixture
URL = "postgresql+asyncpg://crm_test:crm_test@127.0.0.1:56874/crm_template_batch_full_test_20261030"
pytestmark = [pytest.mark.asyncio, pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="需要专用 PostgreSQL")]


@pytest.fixture(autouse=True)
def dedicated_database():
    assert os.getenv("TEST_DATABASE_URL") == URL
    assert os.getenv("DATABASE_URL") == URL


async def apply(env, version, item):
    async with env.sessions() as db:
        view = await preview.create_application_preview(
            db,
            await db.get(User, env.actor),
            env.template,
            ApplicationPreviewRequest.model_validate({"template_version": version, "items": [item]}),
        )
    assert view.items[0].valid, view.items[0].issues
    await confirm(env, view)
    assert await worker(env).run_once()
    async with env.sessions() as db:
        from app.agents.management.templates.models import AgentTemplateBatchItem

        assert (await db.get(AgentTemplateBatchItem, view.items[0].id)).status == "succeeded"


async def publish_v2(env, monkeypatch, config):
    monkeypatch.setattr(service, "get_settings", lambda: env.settings)
    monkeypatch.setattr(service, "review_configured_prompt", AsyncMock(return_value=(10, 2)))
    async with env.sessions() as db:
        template = await db.get(AgentTemplate, env.template)
        user = await db.get(User, env.actor)
        view = await service.update_template(
            db, user, env.template, TemplateUpdate(expected_revision=template.draft_revision, config=config)
        )
        await service.publish_template(db, user, env.template, view.draft_revision)


class Embedding:
    async def embed(self, texts):
        return EmbeddingResult("synthetic", "BAAI/bge-m3", [[1.0] + [0.0] * 1023 for _ in texts], 1, 0, None)


async def test_batch_published_agent_runs_scoped_tools_and_bound_rag(env, monkeypatch):
    customer, conversation, message, run_id, unbound, chunk_id = (uuid.uuid4() for _ in range(6))
    config = env.config.model_copy(deep=True)
    config.description = "负责回答合成订单和政策"
    config.prompt_sections = {
        key: f"第{index}段：仅处理授权业务，证据不足交人工。" for index, (key, _) in enumerate(SECTION_TITLES, 1)
    }
    config.tool_names = ["query_customer_profile"]
    config.knowledge_slots = [KnowledgeSlot(key="policy", name="政策", purpose="依据", required=True)]
    async with env.sessions() as db:
        db.add(Customer(id=customer, store_id=env.store, name="合成买家", order_count=3))
        await db.flush()
        db.add(
            Conversation(
                id=conversation,
                store_id=env.store,
                customer_id=customer,
                platform="tiktok",
                external_conversation_id=conversation.hex,
                status="active",
            )
        )
        await db.flush()
        db.add(
            Message(
                id=message,
                store_id=env.store,
                conversation_id=conversation,
                customer_id=customer,
                platform="tiktok",
                external_message_id=message.hex,
                role="user",
                direction="inbound",
                content="我的订单和政策是什么？",
                status="received",
            )
        )
        db.add(
            KnowledgeFile(
                id=unbound,
                store_id=env.store,
                original_filename="unbound.txt",
                filename_key=unbound.hex,
                active_version_number=1,
            )
        )
        await db.flush()
        db.add(
            KnowledgeFileVersion(
                store_id=env.store,
                file_id=unbound,
                version_number=1,
                source_object_key="synthetic",
                file_sha256="a" * 64,
                media_type="text/plain",
                config_json={},
                status="ready",
                publication_approval="approved_for_internal_review",
                approved_by=env.actor,
                approved_at=datetime.now(UTC),
                created_by=env.actor,
            )
        )
        await db.flush()
        for fid, content, cid in [
            (env.file, "政策要求核实物流轨迹。", chunk_id),
            (unbound, "未绑定秘密政策。", uuid.uuid4()),
            (env.file_other, "外店秘密政策。", uuid.uuid4()),
        ]:
            v = await db.scalar(select(KnowledgeFileVersion).where(KnowledgeFileVersion.file_id == fid))
            v.statement_type = "policy"
            v.customer_scope = "generic"
            db.add(
                KnowledgeFileChunk(
                    id=cid,
                    store_id=v.store_id,
                    file_id=fid,
                    version_id=v.id,
                    unit_index=0,
                    chunk_index=0,
                    content=content,
                    token_count=8,
                    content_hash="b" * 64,
                    strategy="recursive",
                    source_locator={"page": 1},
                    parser_version="test",
                    cleaning_version="test",
                    embedding_model="BAAI/bge-m3",
                    embedding_revision="test",
                    embedding=[1.0] + [0.0] * 1023,
                )
            )
        await db.commit()
    try:
        await publish_v2(env, monkeypatch, config)
        await apply(
            env,
            2,
            {
                "store_id": str(env.store),
                "action": "create",
                "publish": True,
                "enable_after_publish": True,
                "knowledge_mappings": {"policy": [str(env.file)]},
            },
        )
        async with env.sessions() as db:
            agents = tuple(await list_enabled_agents(db, env.store))
            assert len(agents) == 1
            agent = agents[0]
            version = await db.scalar(select(AgentConfigVersion).where(AgentConfigVersion.agent_config_id == agent.id))
            assert version.template_source_json["template_id"] == str(env.template)
            assert version.template_source_json["fields"]["description"]["applied_template_version"] == 2
            assert agent.model_name == "test-model" and agent.tool_names == ("query_customer_profile",)
            assert dict(agent.prompt_sections) == config.prompt_sections
            snap = await freeze_run_context(
                db,
                store_id=env.store,
                conversation_id=conversation,
                trigger_message_id=message,
                published_agents=agents,
                memory_revision=0,
            )
            user = await db.get(User, env.actor)
            permissions = await current_permissions(db, user, env.store)
            before = await db.scalar(
                select(func.count())
                .select_from(Message)
                .where(Message.conversation_id == conversation, Message.direction == "outbound")
            )
            db.add(
                AgentRun(
                    id=run_id,
                    store_id=env.store,
                    conversation_id=conversation,
                    status="running",
                    action="human_review",
                    model_provider="deepseek",
                    model_name="test-model",
                    prompt_version="test",
                    trace_id=run_id.hex,
                )
            )
            await db.commit()
        policy = "政策要求核实物流轨迹。"
        observed = {}
        calls = []

        class Model:
            async def complete(self, *, messages, tools, max_output_tokens):
                names = [t.name for t in tools]
                calls.append(names)
                if names == ["review_answer_evidence"]:
                    payload = json.loads(messages[-1]["content"])
                    evidence = payload["evidence"].values()
                    assert any(
                        item["source"] == str(chunk_id) and item["value"] == observed["policy"] for item in evidence
                    )
                    assert any(
                        item["source"].endswith(".order_count") and item["value"] == str(observed["order_count"])
                        for item in evidence
                    )
                    assert payload["answer"] == observed["answer"]
                    return accepted_review_turn(messages)
                if names == ["route_agents"]:
                    assert "负责回答合成订单和政策" in str(messages)
                    call = FunctionCall(
                        "route",
                        "route_agents",
                        {"selections": [{"agent_id": str(agent.id), "subquestion": "订单和政策"}]},
                    )
                elif names == ["query_customer_profile", "search_knowledge"]:
                    count = sum(m.get("role") == "tool" for m in messages)
                    if count == 0:
                        assert all(value in str(messages) for value in config.prompt_sections.values())
                        call = FunctionCall("profile", "query_customer_profile", {})
                    elif count == 1:
                        result = json.loads(messages[-1]["content"])
                        assert result["status"] == "succeeded" and result["facts"]["order_count"] == 3
                        observed["order_count"] = result["facts"]["order_count"]
                        call = FunctionCall("rag", "search_knowledge", {"query": "物流政策"})
                    else:
                        result = json.loads(messages[-1]["content"])
                        assert result["status"] == "retrieved" and len(result["hits"]) == 1
                        hit = result["hits"][0]
                        assert hit["chunk_id"] == str(chunk_id) and hit["document_version"] == 1
                        assert hit["untrusted_source"] == "knowledge_chunk" and hit["content"] == policy
                        assert "未绑定秘密" not in str(messages) and "外店秘密" not in str(messages)
                        observed["policy"] = hit["content"]
                        answer = f"客户记录有{observed['order_count']}个订单，{observed['policy']}"
                        observed["answer"] = answer
                        return ToolTurn(answer, (), {"role": "assistant", "content": answer}, 3, 2)
                else:
                    assert names == []
                    assert observed["answer"] in str(messages)
                    answer = observed["answer"]
                    return ToolTurn(answer, (), {"role": "assistant", "content": answer}, 3, 2)
                return ToolTurn(
                    None, (call,), {"role": "assistant", "content": None, "tool_calls": [{"id": call.id}]}, 3, 2
                )

        @asynccontextmanager
        async def provider(*args, **kwargs):
            assert args[1:3] == ("deepseek", "test-model")
            yield Model()

        monkeypatch.setattr(execution, "tool_provider", provider)
        monkeypatch.setattr(execution, "session_factory", env.sessions)
        monkeypatch.setattr(factory, "session_factory", env.sessions)
        runtime = SimpleNamespace(embedding_service=Embedding(), reranking_service=None)
        settings = Settings(_env_file=None, LLM_PRIMARY_PROVIDER="deepseek", LLM_PRIMARY_MODEL="test-model")
        result = await execution.execute_model_run(
            snapshot=snap,
            question="我的订单和政策是什么？",
            agents=agents,
            run_id=run_id,
            permissions=permissions,
            trace_id=run_id.hex,
            deadline=time.monotonic() + 30,
            settings=settings,
            runtime=runtime,
            order_id=None,
            live_order=None,
            memory_summary="",
            user=user,
        )
        assert result.phase.value == "review_ready", result
        assert result.suggestion.content == observed["answer"] and result.suggestion.citations == (str(chunk_id),)
        assert [event.name for event in result.specialists[0].tool_events] == [
            "query_customer_profile",
            "search_knowledge",
        ]
        assert calls[-1] == ["review_answer_evidence"]
        async with env.sessions() as db:
            run = await db.get(AgentRun, run_id)
            await execution.persist_dynamic_result(
                db, run=run, result=result, snapshot=snap, agents=agents, mode="formal", elapsed_ms=1
            )
            child = await db.scalar(select(AgentRun).where(AgentRun.parent_run_id == run_id))
            logs = (await db.scalars(select(ToolCall).where(ToolCall.agent_run_id == child.id))).all()
            assert {log.tool_name for log in logs} == {"query_customer_profile", "search_knowledge"}
            assert all(log.status == "succeeded" for log in logs)
            assert child.config_version == agent.config_version == 1
            assert child.agent_config_id == agent.id and child.parent_run_id == run.id
            events = result.specialists[0].tool_events
            citations = result.specialists[0].citations
            assert citations == result.suggestion.citations == (str(chunk_id),)
            assert child.output_summary == f"tool_count={len(events)};citation_count={len(citations)}"
            knowledge_log = next(log for log in logs if log.tool_name == "search_knowledge")
            assert knowledge_log.output_summary == {"succeeded": True, "result_status": "retrieved"}
            assert knowledge_log.agent_run_id == child.id and knowledge_log.input_summary["config_version"] == 1
            assert len(logs) == len(events)
            assert [(event.name, event.status) for event in events] == [
                ("query_customer_profile", "succeeded"),
                ("search_knowledge", "retrieved"),
            ]
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(Message)
                    .where(Message.conversation_id == conversation, Message.direction == "outbound")
                )
                == before
            )
    finally:
        async with env.sessions() as db:
            await db.execute(delete(AuditLog).where(AuditLog.resource_id == run_id))
            await db.commit()


@pytest.mark.parametrize("publish", [False, True])
async def test_create_without_enable_never_enters_formal_candidates(env, publish):
    await apply(env, 1, {"store_id": str(env.store), "action": "create", "publish": publish})
    async with env.sessions() as db:
        config = await db.scalar(select(AgentConfig).where(AgentConfig.store_id == env.store))
        assert config.status == "disabled"
        assert config.published_version == (1 if publish else None)
        assert await list_enabled_agents(db, env.store) == []


async def test_template_changes_do_not_change_running_version_until_new_batch(env, monkeypatch):
    sections = {
        key: f"第{index}段：仅处理授权业务，证据不足交人工。" for index, (key, _) in enumerate(SECTION_TITLES, 1)
    }
    await apply(
        env,
        1,
        {
            "store_id": str(env.store),
            "action": "create",
            "publish": True,
            "enable_after_publish": True,
            "fields": {
                "tool_names": {"choice": "manual", "value": ["search_knowledge"]},
                **{f"prompt_sections.{key}": {"choice": "manual", "value": value} for key, value in sections.items()},
            },
        },
    )
    async with env.sessions() as db:
        first = (await list_enabled_agents(db, env.store))[0]
        approved_at = datetime.now(UTC)
        faq = KnowledgeDocument(
            id=uuid.uuid4(),
            store_id=env.store,
            title="policy",
            question="What is the policy?",
            answer="UNBOUND FAQ SECRET",
            status="published",
            vectorization_status="ready",
            document_version=1,
            content_hash="a" * 64,
            **approved_document_fields(env.actor, approved_at),
        )
        db.add(faq)
        file_version = await db.scalar(select(KnowledgeFileVersion).where(KnowledgeFileVersion.file_id == env.file))
        file_version.statement_type = "policy"
        file_version.customer_scope = "generic"
        db.add(
            KnowledgeFileChunk(
                store_id=env.store,
                file_id=env.file,
                version_id=file_version.id,
                unit_index=0,
                chunk_index=0,
                content="UNBOUND FILE SECRET",
                token_count=4,
                content_hash="b" * 64,
                strategy="recursive",
                source_locator={"page": 1},
                parser_version="test",
                cleaning_version="test",
                embedding_model="BAAI/bge-m3",
                embedding_revision="test",
                embedding=vector(1),
            )
        )
        await db.flush()
        db.add(
            KnowledgeChunk(
                store_id=env.store,
                document_id=faq.id,
                document_version=1,
                chunk_index=0,
                content="UNBOUND FAQ SECRET",
                token_count=4,
                embedding=vector(1),
                metadata_json=approved_chunk_metadata(
                    store_id=env.store, document_version=1, approver_id=env.actor, approved_at=approved_at
                ),
            )
        )
        await db.commit()
        assert first.file_ids == () and dict(first.prompt_sections) == sections
        snapshot = await freeze_debug_context(db, store_id=env.store, conversation_id=None, published_agents=(first,))
        forbidden_search = SimpleNamespace(retrieve=AsyncMock())
        evidence = await retrieve_bound_files(
            session=db,
            snapshot=snapshot,
            agent=first,
            query="policy",
            deadline=time.monotonic() + 10,
            rag_service=forbidden_search,
        )
        assert evidence.hits == ()
        forbidden_search.retrieve.assert_not_awaited()
        config = await db.get(AgentConfig, first.id)
        revision = config.draft_revision
        template = await db.get(AgentTemplate, env.template)
        updated = env.config.model_copy(update={"description": "新模板职责"})
        monkeypatch.setattr(service, "get_settings", lambda: env.settings)
        monkeypatch.setattr(service, "review_configured_prompt", AsyncMock(return_value=(10, 2)))
        view = await service.update_template(
            db,
            await db.get(User, env.actor),
            env.template,
            TemplateUpdate(expected_revision=template.draft_revision, config=updated),
        )
        assert (await list_enabled_agents(db, env.store))[0] == first
        await service.publish_template(db, await db.get(User, env.actor), env.template, view.draft_revision)
        assert (await list_enabled_agents(db, env.store))[0] == first
    await route_candidate(env, monkeypatch, first, first.description)
    await apply(
        env,
        2,
        {
            "store_id": str(env.store),
            "action": "update",
            "agent_id": str(first.id),
            "expected_revision": revision,
            "publish": True,
            "fields": {"description": {"choice": "template"}},
        },
    )
    async with env.sessions() as db:
        second = (await list_enabled_agents(db, env.store))[0]
        assert second.config_version == 2 and second.description == "新模板职责"
        version = await db.scalar(
            select(AgentConfigVersion).where(
                AgentConfigVersion.agent_config_id == first.id, AgentConfigVersion.version == 2
            )
        )
        assert version.template_source_json["fields"]["description"]["applied_template_version"] == 2
    await route_candidate(env, monkeypatch, second, "新模板职责")


async def route_candidate(env, monkeypatch, agent, expected_description):
    calls = []

    class Model:
        async def complete(self, *, messages, tools, max_output_tokens):
            names = [tool.name for tool in tools]
            calls.append(names)
            assert "UNBOUND FAQ SECRET" not in str(messages)
            assert "UNBOUND FILE SECRET" not in str(messages)
            if names == ["route_agents"]:
                if expected_description is not None:
                    assert expected_description in str(messages)
                call = FunctionCall(
                    "route", "route_agents", {"selections": [{"agent_id": str(agent.id), "subquestion": "policy"}]}
                )
                return ToolTurn(None, (call,), {"role": "assistant", "content": None}, 3, 2)
            if names == ["review_answer_evidence"]:
                return accepted_review_turn(messages)
            if names == ["search_knowledge"]:
                assert all(text in str(messages) for text in agent.prompt_sections.values())
                if not any(message.get("role") == "tool" for message in messages):
                    call = FunctionCall("rag", "search_knowledge", {"query": "policy"})
                    return ToolTurn(
                        None, (call,), {"role": "assistant", "content": None, "tool_calls": [{"id": "rag"}]}, 3, 2
                    )
                assert "no_knowledge_bound" in str(messages[-1])
            else:
                assert names == []
            answer = "Unable to confirm; please review."
            return ToolTurn(answer, (), {"role": "assistant", "content": answer}, 3, 2)

    @asynccontextmanager
    async def provider(*args, **kwargs):
        yield Model()

    monkeypatch.setattr(execution, "tool_provider", provider)
    monkeypatch.setattr(execution, "session_factory", env.sessions)
    from app.knowledge_base import vector_port

    legacy_search = AsyncMock(side_effect=AssertionError("FAQ fallback must not run"))
    monkeypatch.setattr(vector_port, "hybrid_search", legacy_search)
    async with env.sessions() as db:
        snapshot = await freeze_debug_context(db, store_id=env.store, conversation_id=None, published_agents=(agent,))
        user = await db.get(User, env.actor)
        permissions = await current_permissions(db, user, env.store)
    run_id = uuid.uuid4()
    result = await execution.execute_model_run(
        snapshot=snapshot,
        question="What is the policy?",
        agents=(agent,),
        run_id=run_id,
        permissions=permissions,
        trace_id=uuid.uuid4().hex,
        deadline=time.monotonic() + 30,
        settings=Settings(_env_file=None, LLM_PRIMARY_PROVIDER="deepseek", LLM_PRIMARY_MODEL="test-model"),
        runtime=None,
        order_id=None,
        live_order=None,
        memory_summary="",
        user=user,
    )
    legacy_search.assert_not_awaited()
    assert result.route.selections[0].agent_id == agent.id
    assert result.phase.value == "review_required"
    assert result.suggestion.content == "Unable to confirm; please review."
    assert result.suggestion.reason_code == "no_verified_evidence"
    assert result.suggestion.citations == ()
    assert result.suggestion.action == "human_review"
    assert result.specialists[0].tool_events[0].name == "search_knowledge"
    async with env.sessions() as db:
        run = AgentRun(
            id=run_id,
            store_id=env.store,
            status="running",
            action="human_review",
            model_provider="deepseek",
            model_name="test-model",
            prompt_version="test",
            trace_id=run_id.hex,
        )
        db.add(run)
        await db.flush()
        await execution.persist_dynamic_result(
            db, run=run, result=result, snapshot=snapshot, agents=(agent,), mode="debug", elapsed_ms=1
        )
        child = await db.scalar(select(AgentRun).where(AgentRun.parent_run_id == run_id))
        assert child.config_version == agent.config_version
        assert (
            await db.scalar(
                select(func.count())
                .select_from(Message)
                .where(Message.store_id == env.store, Message.direction == "outbound")
            )
            == 0
        )
    assert calls[0] == ["route_agents"] and calls[-1] == ["review_answer_evidence"]
