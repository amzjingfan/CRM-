"""Explicit server-side staging acceptance; no send or activation capability.

Run inside the candidate backend environment, from src/backend. Each invocation
uses an existing admin/login session for a memory-only ten-minute credential.
Internal fixture IDs stay in the manifest. Stdout contains low-sensitive counts.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import secrets
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

TEST_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = TEST_ROOT / ".artifacts"
DATASET = TEST_ROOT / "ai/datasets/agent-automation-full-chain-v1.json"
STORES = {"us": "74bd2ebb-53fe-4049-8324-bdf9c24b4d4d", "xbm": "2d9aa744-4f05-42bc-aae9-21223de0adaa"}
DOC_BY_TEMPLATE = {
    "presales_products_v1": "product_guide",
    "order_logistics_us_v13": "shipping_policy",
    "aftersales_products_v1": "aftersales_guide",
    "logistics_update_v1": "notification_guide",
    "reply_fallback_v1": None,
}
UUID_PATTERN = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


class Blocked(RuntimeError):
    """Stable low-sensitive reason only; never attach HTTP/model payloads."""


def digest(value: bytes | str) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def validate_base_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise Blocked("backend_must_be_local_loopback")
    return value.rstrip("/")


def runtime_guard(settings: Any) -> None:
    if settings.app_env != "staging" or settings.real_tiktok_automation_enabled or settings.auto_reply_enabled:
        raise Blocked("staging_and_both_automation_switches_off_required")
    if not (
        settings.llm_enabled
        and settings.agent_v2_formal_enabled
        and settings.agent_debug_enabled
        and settings.agent_v2_debug_enabled
        and settings.embedding_enabled
        and settings.embedding_provider == "local_bge"
        and settings.real_tiktok_read_enabled
        and not settings.allow_mock_platform_adapters
        and settings.llm_primary_provider == "deepseek"
    ):
        raise Blocked("configured_deepseek_bge_debug_formal_required")
    if (
        settings.public_base_url != "https://staging.overselfx.com"
        or settings.public_base_url not in settings.cors_origin_list
    ):
        raise Blocked("unexpected_authenticated_origin")


def request_guard(method: str, path: str) -> None:
    parsed = urlsplit(path)
    if (
        not path.startswith("/v1/")
        or parsed.netloc
        or parsed.scheme
        or parsed.fragment
        or any(part in {"..", "."} for part in parsed.path.split("/"))
        or "%" in parsed.path
    ):
        raise Blocked("request_path_not_allowed")
    allowed = {
        "GET": [
            r"/v1/auth/me",
            r"/v1/agents",
            r"/v1/agents/templates",
            r"/v1/agents/tool-catalog",
            r"/v1/agents/automation",
            r"/v1/agents/logistics-notifications/policy",
            r"/v1/workspace/sessions",
            rf"/v1/workspace/sessions/{UUID_PATTERN}/messages",
            r"/v1/knowledge/files",
            rf"/v1/knowledge/files/{UUID_PATTERN}",
            rf"/v1/knowledge/files/{UUID_PATTERN}/versions/[0-9]+",
            rf"/v1/agents/{UUID_PATTERN}",
            rf"/v1/agents/template-batches/{UUID_PATTERN}",
        ],
        "POST": [
            r"/v1/knowledge/files/imports",
            r"/v1/agents/logistics-notifications/preview",
            rf"/v1/knowledge/files/{UUID_PATTERN}/versions/[0-9]+/approve",
            rf"/v1/agents/templates/{UUID_PATTERN}/application-previews",
            r"/v1/agents/template-batches",
            rf"/v1/agents/{UUID_PATTERN}/(?:disable|debug)",
            rf"/v1/agents/{UUID_PATTERN}/logistics-event-preview",
            rf"/v1/workspace/sessions/{UUID_PATTERN}/(?:suggest|sidebar/search)",
        ],
        "PATCH": [rf"/v1/agents/{UUID_PATTERN}"],
        "DELETE": [rf"/v1/agents/{UUID_PATTERN}", rf"/v1/knowledge/files/{UUID_PATTERN}"],
    }
    if not any(re.fullmatch(pattern, parsed.path) for pattern in allowed.get(method, [])):
        raise Blocked("request_method_or_endpoint_not_allowed")


def new_manifest(dataset_hash: str) -> dict[str, Any]:
    run_id = uuid.uuid4()
    return {
        "schema": 1,
        "run_id": str(run_id),
        "prefix": f"aac_{run_id.hex[:12]}",
        "dataset_sha256": dataset_hash,
        "stores": dict(STORES),
        "assets": [],
        "contexts": {},
        "operations": {},
        "results": [],
        "phase_results": [],
    }


def validate_manifest(state: dict[str, Any], dataset_hash: str | None = None) -> None:
    try:
        run_id = uuid.UUID(state["run_id"])
    except (KeyError, ValueError, TypeError) as error:
        raise Blocked("invalid_manifest_identity") from error
    prefix = f"aac_{run_id.hex[:12]}"
    if (
        state.get("schema") != 1
        or state.get("prefix") != prefix
        or state.get("stores") != STORES
        or (dataset_hash is not None and state.get("dataset_sha256") != dataset_hash)
    ):
        raise Blocked("manifest_scope_or_dataset_mismatch")

    def inspect(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if any(
                    word in key.lower() for word in ("token", "password", "cookie", "csrf", "authorization")
                ) or key in {
                    "content",
                    "text",
                    "title",
                    "address",
                    "buyer_name",
                    "external_order_id",
                    "external_customer_id",
                }:
                    raise Blocked("sensitive_manifest_field_forbidden")
                inspect(item)
        elif isinstance(value, list):
            for item in value:
                inspect(item)

    inspect(state)
    for asset in state.get("assets", []):
        if asset.get("store_id") not in STORES.values() or asset.get("kind") not in {
            "agent",
            "file",
            "message",
            "collaboration",
        }:
            raise Blocked("unowned_manifest_asset")
        try:
            uuid.UUID(asset["id"])
        except (ValueError, TypeError, KeyError) as error:
            raise Blocked("invalid_asset_identity") from error
        if asset["kind"] == "agent" and not asset.get("code", "").startswith(prefix + "_"):
            raise Blocked("unowned_agent_code")
        if asset["kind"] == "file" and not asset.get("filename", "").startswith(prefix + "_"):
            raise Blocked("unowned_file_name")
        if asset["kind"] == "message" and asset.get("marker") != str(run_id):
            raise Blocked("unowned_message_marker")


def manifest_path(path: Path) -> Path:
    path = path.resolve()
    if not path.is_relative_to(ARTIFACT_ROOT.resolve()) or path.suffix != ".json":
        raise Blocked("manifest_must_be_json_under_test_artifacts")
    return path


def save_manifest(path: Path, state: dict[str, Any]) -> None:
    path = manifest_path(path)
    validate_manifest(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def load_manifest(path: Path, dataset_hash: str) -> dict[str, Any]:
    state = json.loads(manifest_path(path).read_text(encoding="utf-8"))
    validate_manifest(state, dataset_hash)
    return state


def case_question(case: dict[str, Any], product: str | None) -> str:
    question = case.get("input", "")
    if not case.get("knowledge") and "Orbit Lamp" in question:
        if not product:
            raise Blocked("real_product_unavailable")
        question = question.replace("Orbit Lamp", product[:70])
        # 真实商品未必是电器；只问平台实际列出的规格，不伪造功率字段。
        question = (
            question.replace("wattage", "listed model or specification")
            .replace("model and power rating", "model and specifications")
            .replace("功率", "商品规格")
            .replace("型号和额定商品规格", "型号和商品规格")
        )
    return question


def answer_checks(
    case: dict[str, Any], answer: dict[str, Any], tools: list[dict[str, Any]], owned_files: set[str], entry: str
) -> dict[str, bool]:
    content = answer.get("content") or ""
    successful = {
        item["name"]
        for item in tools
        if not item.get("mocked")
        and (
            item.get("status") in {"succeeded", "retrieved"}
            or (
                entry == "debug"
                and item["name"] in {"create_handoff_request", "add_internal_note"}
                and item.get("status") == "previewed"
            )
        )
    }
    chinese = sum("\u4e00" <= char <= "\u9fff" for char in content)
    letters = sum(char.isascii() and char.isalpha() for char in content)
    fact = str(case.get("expected_fact", ""))
    normalized = "".join(content.lower().split())
    checks = {
        "nonempty": bool(content.strip()),
        "no_send": answer.get("send_performed") is False,
        "concise": 0 < len(content.encode("utf-16-le")) // 2 <= 2000,
        "required_tools": set(case.get("required_tools", [])) <= successful,
        "language": chinese > 0 if case["language"] == "zh-CN" else letters > 0 and chinese < max(5, letters // 5),
        "expected_fact": not fact or "".join(fact.lower().split()) in normalized,
    }
    if case.get("knowledge"):
        checks["owned_citation"] = any(
            str(item.get("document_id")) in owned_files
            for item in answer.get("citations", [])
            if isinstance(item, dict)
        )
    if case.get("scenario") == "three_unresolved":
        checks["exact_fixed_fallback"] = content == case["expected_answer"]
    return checks


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("inventory", "prepare", "run", "cleanup"), required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--enable-live", action="store_true")
    parser.add_argument("--entry", choices=("debug", "suggest"), default="debug")
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--store", action="append", choices=tuple(STORES), default=[])
    parser.add_argument("--budget-seconds", type=int, default=540)
    args = parser.parse_args(argv)
    if not args.enable_live:
        parser.error("explicit --enable-live required")
    if not 1 <= args.budget_seconds <= 540:
        parser.error("budget must be 1..540 seconds")
    return args


async def admin_identity() -> tuple[str, uuid.UUID]:
    from sqlalchemy import select

    from app.auth.security import create_token
    from app.shared.database.base import Role, User, UserLoginSession
    from app.shared.database.session import session_factory

    async with session_factory() as session:
        users = (
            (await session.scalars(select(User).join(User.roles).where(Role.code == "admin", User.status == "active")))
            .unique()
            .all()
        )
        if len(users) != 1:
            raise Blocked("one_active_existing_admin_required")
        user = users[0]
        login = await session.scalar(
            select(UserLoginSession)
            .where(
                UserLoginSession.user_id == user.id,
                UserLoginSession.revoked_at.is_(None),
                UserLoginSession.expires_at > datetime.now(UTC),
            )
            .order_by(UserLoginSession.expires_at.desc())
            .limit(1)
        )
        if login is None:
            raise Blocked("existing_valid_login_session_required")
        return create_token(user.id, "access", timedelta(minutes=10), user.auth_version or 0, login.id), user.id


class Runner:
    def __init__(
        self, args: argparse.Namespace, state: dict[str, Any], dataset: dict[str, Any], client: httpx.AsyncClient
    ):
        self.args, self.state, self.dataset, self.client = args, state, dataset, client
        self.live: dict[str, Any] = {}
        self.actor_id: uuid.UUID | None = None

    def save(self) -> None:
        save_manifest(self.args.manifest, self.state)

    def asset(self, kind: str, store: str, key: str) -> dict[str, Any] | None:
        return next(
            (
                item
                for item in self.state["assets"]
                if item["kind"] == kind and item["store_id"] == STORES[store] and item.get("key") == key
            ),
            None,
        )

    async def api(
        self,
        method: str,
        path: str,
        *,
        operation: str | None = None,
        payload: Any = None,
        files: Any = None,
        form: Any = None,
        allowed: tuple[int, ...] = (200,),
    ) -> Any:
        request_guard(method, path)
        if method == "PATCH" and (
            not isinstance(payload, dict)
            or set(payload) != {"knowledge_file_ids", "expected_revision"}
            or payload["knowledge_file_ids"] != []
        ):
            raise Blocked("only_owned_cleanup_file_unbinding_allowed")
        if path.endswith("/approve") and (not isinstance(payload, dict) or payload.get("purpose") != "internal_review"):
            raise Blocked("synthetic_public_approval_forbidden")
        if path.endswith("/application-previews") and any(
            item.get("action") != "create"
            or item.get("store_id") not in STORES.values()
            or not item.get("code", "").startswith(self.state["prefix"] + "_")
            for item in payload.get("items", [])
        ):
            raise Blocked("template_changes_must_create_owned_agents_only")
        headers = {}
        model_call = (
            path.endswith(("/suggest", "/debug", "/logistics-event-preview"))
            or path == "/v1/agents/logistics-notifications/preview"
        )
        if method != "GET":
            key = operation or f"{method}:{path}:{digest(json.dumps(payload, sort_keys=True))}"
            record = self.state["operations"].setdefault(key, {"idempotency_key": str(uuid.uuid4()), "state": "new"})
            if record["state"] in {"started", "unknown"} and model_call:
                raise Blocked("model_response_unknown_do_not_replay")
            record["state"] = "started"
            self.save()
            headers["Idempotency-Key"] = record["idempotency_key"]
        try:
            response = await self.client.request(method, path, json=payload, files=files, data=form, headers=headers)
        except httpx.HTTPError as error:
            if method != "GET":
                record["state"] = "unknown"
                self.save()
            raise Blocked("api_transport_unknown") from error
        if response.status_code not in allowed:
            if method != "GET":
                record["state"] = "unknown" if model_call or response.status_code >= 500 else "failed"
                self.save()
            raise Blocked(f"api_http_{response.status_code}")
        if response.status_code in {204, 404}:
            result = None
        else:
            try:
                body = response.json()
                if body.get("code") != 0:
                    raise ValueError("envelope")
                result = body.get("data")
            except (ValueError, AttributeError) as error:
                if method != "GET":
                    record["state"] = "unknown"
                    self.save()
                raise Blocked("api_response_unrecoverable") from error
        if method != "GET":
            record["state"] = "completed"
            self.save()
        return result

    async def context(self, store: str, conversation_id: str) -> dict[str, Any]:
        detail = await self.api("GET", f"/v1/workspace/sessions/{conversation_id}/messages?page_size=1")
        if detail["session"]["store_id"] != STORES[store] or detail["session"]["status"] not in {
            "active",
            "transferred",
        }:
            raise Blocked("conversation_scope_changed")
        orders = await self.api(
            "POST",
            f"/v1/workspace/sessions/{conversation_id}/sidebar/search",
            payload={"section": "orders", "field": "order_id", "query": ""},
        )
        products = await self.api(
            "POST",
            f"/v1/workspace/sessions/{conversation_id}/sidebar/search",
            payload={"section": "products", "field": "name", "query": ""},
        )
        product = next(
            (
                item
                for item in products.get("items", [])
                if any((sku.get("quantity") or 0) > 0 for sku in item.get("skus", []))
            ),
            None,
        )
        return {"conversation_id": conversation_id, "orders": orders.get("items", []), "product": product}

    async def inventory(self) -> None:
        from sqlalchemy import select

        from app.conversations.models import Message
        from app.shared.database.session import session_factory

        for store in self.args.store or STORES:
            selected = None
            for page in range(1, 6):
                result = await self.api(
                    "GET",
                    f"/v1/workspace/sessions?store_id={STORES[store]}&platform=tiktok&status=active&page_size=50&page={page}",
                )
                for candidate in result.get("items", []):
                    async with session_factory() as session:
                        trigger = await session.scalar(
                            select(Message.id)
                            .where(
                                Message.store_id == uuid.UUID(STORES[store]),
                                Message.conversation_id == uuid.UUID(candidate["id"]),
                                Message.direction == "inbound",
                                Message.role == "user",
                                Message.external_message_id.op("~")(r"^[0-9]+$"),
                            )
                            .order_by(Message.created_at.desc(), Message.id.desc())
                            .limit(1)
                        )
                    if trigger is None:
                        continue
                    try:
                        context = await self.context(store, candidate["id"])
                    except Blocked:
                        continue
                    if context["orders"]:
                        selected = {
                            "conversation_id": candidate["id"],
                            "trusted_trigger_id": str(trigger),
                            "has_order": True,
                            "has_product": context["product"] is not None,
                        }
                        break
                if selected or not result.get("items"):
                    break
            if selected is None:
                raise Blocked(f"{store}_real_buyer_order_context_unavailable")
            catalog = await self.api("GET", f"/v1/agents/tool-catalog?store_id={STORES[store]}")
            selected["unavailable_tools"] = [
                item["name"] for item in catalog["tools"] if item["availability"] == "unavailable"
            ]
            self.state["contexts"][store] = selected
            self.save()

    async def wait(self, path: str, *, batch: bool = False) -> Any:
        for _ in range(65):
            result = await self.api("GET", path)
            if batch:
                if result.get("items") and all(item["status"] == "succeeded" for item in result["items"]):
                    return result
                if any(
                    item["status"] in {"failed", "needs_repreview", "cancelled"} for item in result.get("items", [])
                ):
                    raise Blocked("template_batch_not_successful")
            else:
                if result["status"] == "ready":
                    return result
                if result["status"] in {"failed_final", "failed_retryable", "review_required"}:
                    raise Blocked("document_not_ready")
            await asyncio.sleep(2)
        raise Blocked("asset_processing_deadline")

    async def prepare(self) -> None:
        templates = {item["code"]: item for item in (await self.api("GET", "/v1/agents/templates"))["items"]}
        for store in self.args.store or STORES:
            if store not in self.state["contexts"]:
                raise Blocked("inventory_required")
            for document in self.dataset["documents"]:
                asset = self.asset("file", store, document["key"])
                if asset is None:
                    filename = f"{self.state['prefix']}_{store}_{document['key']}.txt"
                    matches = [
                        item
                        for item in (
                            await self.api(
                                "GET", f"/v1/knowledge/files?store_id={STORES[store]}&page_size=100&search={filename}"
                            )
                        )["items"]
                        if item["filename"] == filename
                    ]
                    if len(matches) > 1:
                        raise Blocked("duplicate_owned_filename")
                    if matches:
                        value = matches[0]
                        result = {"file_id": value["id"], "version_number": value["latest_version"]["version_number"]}
                    else:
                        result = await self.api(
                            "POST",
                            "/v1/knowledge/files/imports",
                            operation=f"import:{store}:{document['key']}",
                            files={"file": (filename, document["text"].encode(), "text/plain")},
                            form={"store_id": STORES[store], "config_json": "{}"},
                            allowed=(202,),
                        )
                    asset = {
                        "kind": "file",
                        "key": document["key"],
                        "store_id": STORES[store],
                        "id": result["file_id"],
                        "version": result["version_number"],
                        "filename": filename,
                        "sha256": digest(document["text"]),
                    }
                    self.state["assets"].append(asset)
                    self.save()
                detail = await self.wait(f"/v1/knowledge/files/{asset['id']}/versions/{asset['version']}")
                if detail["file_sha256"] != asset["sha256"]:
                    raise Blocked("owned_file_digest_changed")
                if detail["approval_status"] == "draft":
                    detail = await self.api(
                        "POST",
                        f"/v1/knowledge/files/{asset['id']}/versions/{asset['version']}/approve",
                        payload={"statement_type": "policy", "customer_scope": "generic", "purpose": "internal_review"},
                    )
                if detail["approval_status"] != "approved_for_internal_review":
                    raise Blocked("synthetic_file_must_remain_internal_only")
            for code, document_key in DOC_BY_TEMPLATE.items():
                known_agent = self.asset("agent", store, code)
                if known_agent and known_agent.get("prepared"):
                    continue
                template = templates.get(code)
                if template is None or not template.get("published_version"):
                    raise Blocked("required_published_template_unavailable")
                config = template.get("published_config") or template["config"]
                owned_code = f"{self.state['prefix']}_{store}_{code}"
                agents = await self.api("GET", "/v1/agents")
                matches = [item for item in agents if item["store_id"] == STORES[store] and item["code"] == owned_code]
                if len(matches) > 1:
                    raise Blocked("duplicate_owned_agent_code")
                if matches:
                    result_agent = matches[0]
                else:
                    batch_id = self.state.get("batches", {}).get(f"{store}:{code}")
                    if batch_id is None:
                        prior_apply = self.state["operations"].get(f"apply:{store}:{code}")
                        if prior_apply and prior_apply["state"] in {"started", "unknown"}:
                            raise Blocked("template_batch_response_unknown_reconcile_required")
                        file = self.asset("file", store, document_key) if document_key else None
                        mappings = (
                            {slot["key"]: [file["id"]] for slot in config.get("knowledge_slots", [])} if file else {}
                        )
                        preview = await self.api(
                            "POST",
                            f"/v1/agents/templates/{template['id']}/application-previews",
                            payload={
                                "template_version": template["published_version"],
                                "items": [
                                    {
                                        "store_id": STORES[store],
                                        "action": "create",
                                        "name": owned_code,
                                        "code": owned_code,
                                        "knowledge_mappings": mappings,
                                        "publish": True,
                                        "enable_after_publish": True,
                                    }
                                ],
                            },
                        )
                        if not preview["items"][0]["valid"]:
                            raise Blocked("template_application_preview_invalid")
                        batch = await self.api(
                            "POST",
                            "/v1/agents/template-batches",
                            operation=f"apply:{store}:{code}",
                            payload={"preview_id": preview["preview_id"], "confirmation": True},
                        )
                        self.state.setdefault("batches", {})[f"{store}:{code}"] = batch["id"]
                        self.save()
                        batch_id = batch["id"]
                    applied = await self.wait(f"/v1/agents/template-batches/{batch_id}", batch=True)
                    result_agent = await self.api("GET", f"/v1/agents/{applied['items'][0]['result_agent_id']}")
                owned_asset = self.asset("agent", store, code)
                if owned_asset is None:
                    owned_asset = {
                        "kind": "agent",
                        "key": code,
                        "store_id": STORES[store],
                        "id": result_agent["id"],
                        "code": owned_code,
                    }
                    self.state["assets"].append(owned_asset)
                owned_asset.update(
                    revision=result_agent["draft_revision"],
                    version=result_agent["published_version"],
                    tools=result_agent["enabled_tools"],
                )
                self.save()
                if result_agent["template_id"] != template["id"]:
                    raise Blocked("owned_agent_template_mismatch")
                if (
                    document_key
                    and self.asset("file", store, document_key)["id"] not in result_agent["knowledge_file_ids"]
                ):
                    raise Blocked("template_has_no_required_knowledge_mapping")
                owned_asset["prepared"] = True
                self.save()

    async def trigger(self, store: str, key: str, question: str, language: str) -> str:
        from sqlalchemy import select

        from app.agents.tools.access import current_permissions
        from app.conversations.models import Conversation, Message
        from app.shared.database.base import User
        from app.shared.database.session import session_factory

        context = self.state["contexts"][store]
        asset = self.asset("message", store, key)
        if asset is None:
            asset = {
                "kind": "message",
                "key": key,
                "store_id": STORES[store],
                "id": str(uuid.uuid4()),
                "marker": self.state["run_id"],
                "conversation_id": context["conversation_id"],
                "sha256": digest(question),
            }
            self.state["assets"].append(asset)
            self.save()
        if asset["sha256"] != digest(question):
            raise Blocked("synthetic_question_changed_on_resume")
        async with session_factory() as session:
            actor = await session.get(User, self.actor_id, populate_existing=True) if self.actor_id else None
            if (
                actor is None
                or actor.status != "active"
                or not {"workspace.view", "workspace.reply"}
                <= await current_permissions(session, actor, uuid.UUID(STORES[store]))
            ):
                raise Blocked("synthetic_fixture_current_authorization_required")
            conversation = await session.get(Conversation, uuid.UUID(context["conversation_id"]))
            if conversation is None or str(conversation.store_id) != STORES[store] or conversation.platform != "tiktok":
                raise Blocked("synthetic_trigger_scope_invalid")
            latest = await session.scalar(
                select(Message.id)
                .where(
                    Message.conversation_id == conversation.id,
                    Message.store_id == conversation.store_id,
                    Message.direction == "inbound",
                    Message.role == "user",
                    Message.external_message_id.op("~")(r"^[0-9]+$"),
                )
                .order_by(Message.created_at.desc(), Message.id.desc())
                .limit(1)
            )
            if str(latest) != context["trusted_trigger_id"]:
                raise Blocked("real_buyer_context_changed")
            existing = await session.get(Message, uuid.UUID(asset["id"]))
            if existing is not None:
                if (
                    existing.raw_payload.get("acceptance_run_id") != self.state["run_id"]
                    or str(existing.store_id) != asset["store_id"]
                    or str(existing.conversation_id) != asset["conversation_id"]
                    or existing.direction != "inbound"
                    or existing.role != "user"
                    or digest(existing.content) != asset["sha256"]
                ):
                    raise Blocked("unknown_existing_trigger")
                return asset["id"]
            # 只插入精确标记的内部验收输入，不调用Webhook/入站/派单或发送链路，不改变会话指针。
            session.add(
                Message(
                    id=uuid.UUID(asset["id"]),
                    store_id=conversation.store_id,
                    conversation_id=conversation.id,
                    customer_id=conversation.customer_id,
                    platform="tiktok",
                    external_message_id=f"acceptance-{self.state['run_id']}-{uuid.uuid4()}",
                    idempotency_key=f"fixture:{self.state['run_id']}:{asset['id']}",
                    role="user",
                    direction="inbound",
                    message_type="text",
                    content=question,
                    language=language,
                    status="received",
                    created_at=datetime.now(UTC),
                    raw_payload={
                        "synthetic_acceptance": True,
                        "acceptance_run_id": self.state["run_id"],
                        "case_key": key,
                    },
                )
            )
            await session.commit()
        return asset["id"]

    async def traces(self, store: str, run_id: str) -> tuple[list[dict[str, Any]], set[str], str | None]:
        from sqlalchemy import or_, select

        from app.agents.runtime.models import AgentRun
        from app.agents.tools.models import AgentCollaborationEntry
        from app.shared.database.session import session_factory
        from app.tools.models import ToolCall

        async with session_factory() as session:
            root = await session.get(AgentRun, uuid.UUID(run_id))
            if (
                root is None
                or str(root.store_id) != STORES[store]
                or str(root.conversation_id) != self.state["contexts"][store]["conversation_id"]
            ):
                raise Blocked("run_scope_mismatch")
            if root.status != "succeeded":
                raise Blocked("model_run_not_successful")
            nodes = (
                await session.scalars(
                    select(AgentRun).where(
                        AgentRun.store_id == root.store_id,
                        or_(AgentRun.id == root.id, AgentRun.parent_run_id == root.id),
                    )
                )
            ).all()
            calls = (
                await session.scalars(
                    select(ToolCall).where(
                        ToolCall.store_id == root.store_id, ToolCall.agent_run_id.in_([node.id for node in nodes])
                    )
                )
            ).all()
            tools = [
                {
                    "name": item.tool_name,
                    "status": (item.output_summary or {}).get("result_status", item.status),
                    "mocked": item.mocked,
                }
                for item in calls
            ]
            collaboration = (
                await session.scalars(
                    select(AgentCollaborationEntry).where(
                        AgentCollaborationEntry.store_id == root.store_id,
                        AgentCollaborationEntry.agent_run_id.in_([node.id for node in nodes]),
                    )
                )
            ).all()
            for item in collaboration:
                if not any(asset["id"] == str(item.id) for asset in self.state["assets"]):
                    self.state["assets"].append(
                        {"kind": "collaboration", "id": str(item.id), "store_id": STORES[store], "run_id": run_id}
                    )
            self.save()
            return (
                tools,
                {str(node.agent_config_id) for node in nodes if node.parent_run_id == root.id},
                root.error_code,
            )

    async def suggest(self, store: str, case_key: str, question: str, language: str) -> dict[str, Any]:
        trigger_id = await self.trigger(store, case_key, question, language)
        return await self.api(
            "POST",
            f"/v1/workspace/sessions/{self.state['contexts'][store]['conversation_id']}/suggest",
            operation=f"suggest:{store}:{case_key}",
            payload={"trigger_message_id": trigger_id},
        )

    async def event_preview(self, store: str, case: dict[str, Any], asset: dict[str, Any]) -> dict[str, Any]:
        from sqlalchemy import select

        from app.knowledge_base.document_models import KnowledgeFileChunk
        from app.shared.database.session import session_factory

        policy = await self.api("GET", f"/v1/agents/logistics-notifications/policy?store_id={STORES[store]}")
        if policy.get("agent_id") != asset["id"]:
            raise Blocked("event_needs_isolated_simulation_or_explicit_owned_policy_binding")
        context = await self.context(store, self.state["contexts"][store]["conversation_id"])
        if not context["orders"]:
            raise Blocked("event_real_buyer_order_unavailable")
        order = context["orders"][0]
        before = await outbound_counts([store])
        if self.args.entry == "debug":
            result = await self.api(
                "POST",
                f"/v1/agents/{asset['id']}/logistics-event-preview",
                operation=f"event:{store}:debug:{case['id']}",
                payload={
                    "conversation_id": context["conversation_id"],
                    "external_order_id": order["external_order_id"],
                },
            )
        else:
            result = await self.api(
                "POST",
                "/v1/agents/logistics-notifications/preview",
                operation=f"event:{store}:suggest:{case['id']}",
                payload={
                    "store_id": STORES[store],
                    "conversation_id": context["conversation_id"],
                    "order_id": order["id"],
                },
            )
        after = await outbound_counts([store])
        owned_file = self.asset("file", store, "notification_guide")
        citations = [uuid.UUID(value) for value in result.get("citations", [])]
        async with session_factory() as session:
            matched = (
                await session.scalar(
                    select(KnowledgeFileChunk.id)
                    .where(
                        KnowledgeFileChunk.id.in_(citations),
                        KnowledgeFileChunk.store_id == uuid.UUID(STORES[store]),
                        KnowledgeFileChunk.file_id == uuid.UUID(owned_file["id"]),
                    )
                    .limit(1)
                )
                if owned_file
                else None
            )
        tools = {
            item.get("name") or item.get("tool_name")
            for item in result.get("tool_calls", [])
            if item.get("status") in {"succeeded", "retrieved"}
        }
        checks = {
            "readonly_preview": result.get("status") == "previewed",
            "observed_no_outbound": before == after,
            "required_tools": set(case["required_tools"]) <= tools,
            "owned_citation": matched is not None,
            "language": result.get("buyer_language") == case["language"],
            "concise": 0 < len((result.get("preview_text") or "").encode("utf-16-le")) // 2 <= 2000,
        }
        # 当前真实节点预演不能冒充数据集的虚构新/旧/重复/乱序事件模拟。
        return {
            "store": store,
            "case": case["id"],
            "entry": self.args.entry,
            "status": "blocked",
            "reason": "live_preview_observed_isolated_simulation_still_required",
            "source": "live_verified_latest_event",
            "live_preview_checks": checks,
            "live_preview_passed": all(checks.values()),
            "citation_count": len(citations),
            "successful_tools": sorted(tools),
        }

    async def run_case(self, store: str, case: dict[str, Any]) -> dict[str, Any]:
        key = f"{self.args.entry}:{case['id']}"
        asset = self.asset("agent", store, case["agent"])
        if asset is None or not asset.get("prepared"):
            raise Blocked("prepare_owned_agent_required")
        current = await self.api("GET", f"/v1/agents/{asset['id']}")
        if (
            current.get("store_id") != asset["store_id"]
            or current.get("code") != asset["code"]
            or current.get("draft_revision") != asset["revision"]
            or current.get("published_version") != asset["version"]
            or current.get("status") != "enabled"
        ):
            raise Blocked("owned_agent_changed_since_prepare")
        gate = await self.api("GET", f"/v1/agents/automation?store_id={STORES[store]}")
        if gate.get("global_enabled") is not False:
            raise Blocked("candidate_backend_automation_must_remain_off")
        if set(case.get("required_tools", [])) & set(self.state["contexts"][store]["unavailable_tools"]):
            raise Blocked("required_tool_capability_unavailable")
        if case.get("scenario") == "logistics_event":
            return await self.event_preview(store, case, asset)
        files = {
            item["id"]
            for item in self.state["assets"]
            if item["kind"] == "file" and item["store_id"] == STORES[store] and item["key"] == case.get("knowledge")
        }
        conversation_id = self.state["contexts"][store]["conversation_id"]
        if case.get("scenario") == "three_unresolved":
            reset_case = next(item for item in self.dataset["cases"] if item["id"] == "presales_knowledge_en")
            reset = await self.suggest(store, f"{key}:reset", reset_case["input"], "en")
            reset_tools, _, reset_reason = await self.traces(store, reset["agent_run_id"])
            product_files = {
                item["id"]
                for item in self.state["assets"]
                if item["kind"] == "file" and item["store_id"] == STORES[store] and item["key"] == "product_guide"
            }
            if reset_reason or not all(
                answer_checks(reset_case, reset, reset_tools, product_files, "suggest").values()
            ):
                raise Blocked("fallback_resolved_reset_not_verified")
            for index, question in enumerate(case["inputs"][:2]):
                previous = await self.suggest(store, f"{key}:prior:{index}", question, case["language"])
                _, _, reason = await self.traces(store, previous["agent_run_id"])
                if reason != "no_matching_agent":
                    raise Blocked("fallback_needs_two_real_no_matching_agent_outcomes")
                self.state["results"].append(
                    {
                        "store": store,
                        "case": case["id"],
                        "entry": "prerequisite",
                        "turn": index + 1,
                        "run_id": previous["agent_run_id"],
                        "status": "verified_no_matching_agent",
                    }
                )
                self.save()
            question = case["inputs"][2]
        else:
            if store not in self.live:
                self.live[store] = await self.context(store, conversation_id)
            live = self.live[store]
            product = live["product"]["title"] if live["product"] else None
            order_case = (
                case["id"].startswith("order_") or case["id"].startswith("aftersales_progress")
            ) and not case.get("knowledge")
            if order_case:
                if not live["orders"] or not live["orders"][0].get("items"):
                    raise Blocked("real_order_product_context_unavailable")
                product = live["orders"][0]["items"][0]["name"]
            question = case_question(case, product)
            if order_case:
                question += "\nOrder number: " + live["orders"][0]["external_order_id"]
        if self.args.entry == "suggest":
            answer = await self.suggest(store, key, question, case["language"])
        else:
            answer = await self.api(
                "POST",
                f"/v1/agents/{asset['id']}/debug",
                operation=f"debug:{store}:{key}",
                payload={"message": question, "conversation_id": conversation_id, "mode": "single"},
            )
        tools, participants, reason = await self.traces(store, answer["agent_run_id"])
        checks = answer_checks(case, answer, tools, files, self.args.entry)
        checks["owned_target_participated"] = asset["id"] in participants
        checks["review_result"] = (
            reason == "fallback_third_round" if case.get("scenario") == "three_unresolved" else reason is None
        )
        return {
            "store": store,
            "case": case["id"],
            "entry": self.args.entry,
            "status": "pass" if all(checks.values()) else "fail",
            "assertions": checks,
            "run_id": answer["agent_run_id"],
            "citation_count": len(answer.get("citations", [])),
            "successful_tools": sorted(
                {item["name"] for item in tools if item["status"] in {"succeeded", "retrieved"}}
            ),
            "previewed_tools": sorted({item["name"] for item in tools if item["status"] == "previewed"}),
            "semantic_language_review": "heuristic_requires_final_review",
        }

    async def run(self) -> None:
        cases = [case for case in self.dataset["cases"] if not self.args.case or case["id"] in self.args.case]
        if not cases or set(self.args.case) - {case["id"] for case in cases}:
            raise Blocked("unknown_selected_case")
        for store in self.args.store or STORES:
            if store not in self.state["contexts"]:
                raise Blocked("inventory_required")
            for case in cases:
                if any(
                    item.get("store") == store
                    and item.get("case") == case["id"]
                    and item.get("entry") == self.args.entry
                    and item.get("status") == "pass"
                    for item in self.state["results"]
                ):
                    continue
                started = time.monotonic()
                try:
                    result = await self.run_case(store, case)
                except Blocked as error:
                    result = {
                        "store": store,
                        "case": case["id"],
                        "entry": self.args.entry,
                        "status": "blocked",
                        "reason": str(error),
                    }
                except Exception as error:
                    result = {
                        "store": store,
                        "case": case["id"],
                        "entry": self.args.entry,
                        "status": "blocked",
                        "reason": type(error).__name__,
                    }
                result["duration_ms"] = int((time.monotonic() - started) * 1000)
                self.state["results"].append(result)
                self.save()

    async def collect_owned_collaboration(self) -> None:
        # 无登记输入时不导入应用配置；保持空清理与离线安全测试完全不接触运行环境。
        messages = [uuid.UUID(item["id"]) for item in self.state["assets"] if item["kind"] == "message"]
        if not messages:
            return
        from sqlalchemy import select

        from app.agents.runtime.models import AgentRun
        from app.agents.tools.models import AgentCollaborationEntry
        from app.shared.database.session import session_factory

        # 即便正式HTTP响应丢失，也按已登记触发消息追溯内部记录；只读，不删除审计或未知数据。
        async with session_factory() as session:
            runs = select(AgentRun.id).where(
                AgentRun.trigger_message_id.in_(messages),
                AgentRun.store_id.in_([uuid.UUID(value) for value in STORES.values()]),
            )
            records = (
                await session.scalars(
                    select(AgentCollaborationEntry).where(
                        AgentCollaborationEntry.agent_run_id.in_(runs),
                        AgentCollaborationEntry.store_id.in_([uuid.UUID(value) for value in STORES.values()]),
                    )
                )
            ).all()
            known = {item["id"] for item in self.state["assets"]}
            for row in records:
                if str(row.id) not in known:
                    self.state["assets"].append(
                        {
                            "kind": "collaboration",
                            "id": str(row.id),
                            "store_id": str(row.store_id),
                            "run_id": str(row.agent_run_id),
                        }
                    )
        self.save()

    async def cleanup(self) -> None:
        await self.collect_owned_collaboration()
        if any(
            key.startswith(("apply:", "import:")) and value["state"] in {"started", "unknown"}
            for key, value in self.state["operations"].items()
        ):
            raise Blocked("unresolved_creations_reconcile_prepare_before_cleanup")
        for batch_key in self.state.get("batches", {}):
            store, code = batch_key.split(":", 1)
            if not self.asset("agent", store, code):
                raise Blocked("pending_batch_reconcile_prepare_before_cleanup")
        for kind in ("agent", "file", "message", "collaboration"):
            for asset in [
                item
                for item in self.state["assets"]
                if item["kind"] == kind
                and item["store_id"] in {STORES[store] for store in self.args.store or STORES}
                and not item.get("cleaned")
            ]:
                if kind in {"message", "collaboration"}:
                    asset["root_cleanup_required"] = True
                    self.save()
                    continue
                base = f"/v1/agents/{asset['id']}" if kind == "agent" else f"/v1/knowledge/files/{asset['id']}"
                value = await self.api("GET", base, allowed=(200, 404))
                if value is None:
                    asset["cleaned"] = True
                    self.save()
                    continue
                if value.get("store_id") != asset["store_id"]:
                    raise Blocked("cleanup_scope_mismatch")
                if kind == "agent":
                    if (
                        value.get("code") != asset["code"]
                        or value.get("draft_revision") != asset["revision"]
                        or value.get("published_version") != asset["version"]
                    ):
                        raise Blocked("owned_agent_modified_cleanup_blocked")
                    if value["status"] == "enabled":
                        await self.api("POST", base + "/disable")
                    if value.get("knowledge_file_ids"):
                        updated = await self.api(
                            "PATCH", base, payload={"expected_revision": asset["revision"], "knowledge_file_ids": []}
                        )
                        asset["revision"] = updated["draft_revision"]
                        self.save()
                else:
                    if (
                        value.get("filename") != asset["filename"]
                        or value.get("active_version_number") != asset["version"]
                    ):
                        raise Blocked("owned_file_modified_cleanup_blocked")
                    detail = await self.api("GET", base + f"/versions/{asset['version']}")
                    if detail.get("file_sha256") != asset["sha256"]:
                        raise Blocked("owned_file_modified_cleanup_blocked")
                await self.api("DELETE", base, allowed=(204,))
                asset["cleaned"] = True
                self.save()
        if any(item.get("root_cleanup_required") for item in self.state["assets"]):
            raise Blocked("exact_owned_messages_collaboration_memory_need_root_cleanup_no_delete_api")


async def outbound_counts(stores: list[str]) -> dict[str, int]:
    from sqlalchemy import func, select

    from app.conversations.models import Message
    from app.shared.database.session import session_factory

    async with session_factory() as session:
        return {
            store: int(
                (
                    await session.scalar(
                        select(func.count())
                        .select_from(Message)
                        .where(Message.store_id == uuid.UUID(STORES[store]), Message.direction == "outbound")
                    )
                )
                or 0
            )
            for store in stores
        }


async def execute(args: argparse.Namespace) -> int:
    # 延迟导入应用，离线测试不会读取运行配置或认证材料。
    backend = TEST_ROOT.parent / "backend"
    if backend.exists():
        sys.path.insert(0, str(backend))
    elif (Path.cwd() / "app").is_dir():
        sys.path.insert(0, str(Path.cwd()))
    from app.shared.config.settings import get_settings
    from app.shared.database import models as registered_models  # noqa: F401

    settings = get_settings()
    runtime_guard(settings)
    base_url = validate_base_url(args.base_url)
    path = manifest_path(args.manifest)
    raw = DATASET.read_bytes()
    dataset = json.loads(raw)
    if dataset.get("external_test_sending") is not False:
        raise Blocked("dataset_external_sending_forbidden")
    state = load_manifest(path, digest(raw)) if path.exists() else new_manifest(digest(raw))
    if not path.exists() and args.phase != "inventory":
        raise Blocked("new_manifest_requires_inventory")
    save_manifest(path, state)
    token, actor_id = await admin_identity()
    csrf = secrets.token_urlsafe(24)
    status, reason = "completed", None
    before = after = None
    async with httpx.AsyncClient(
        base_url=base_url,
        cookies={"crm_access_token": token, "crm_csrf_token": csrf},
        headers={"Origin": settings.public_base_url, "X-CSRF-Token": csrf},
        timeout=httpx.Timeout(170),
        follow_redirects=False,
        trust_env=False,
    ) as client:
        runner = Runner(args, state, dataset, client)
        runner.actor_id = actor_id
        try:
            async with asyncio.timeout(args.budget_seconds):
                identity = await runner.api("GET", "/v1/auth/me")
                if identity.get("id") != str(actor_id):
                    raise Blocked("api_identity_mismatch")
                before = await outbound_counts(list(args.store or STORES))
                await getattr(runner, args.phase)()
                after = await outbound_counts(list(args.store or STORES))
                if before != after:
                    raise Blocked("outbound_ledger_changed_requires_root_review")
        except TimeoutError:
            status, reason = "blocked", "phase_deadline_reached_resume_manifest"
        except Blocked as error:
            status, reason = "blocked", str(error)
        except Exception as error:
            status, reason = "blocked", type(error).__name__
        if args.phase == "run" and any(item.get("status") in {"fail", "blocked"} for item in state["results"]):
            status = "blocked"
        state["phase_results"].append(
            {
                "phase": args.phase,
                "status": status,
                "reason": reason,
                "outbound_unchanged": before is not None and before == after,
            }
        )
        save_manifest(path, state)
    counts = {
        name: sum(item.get("status") == name for item in state["results"]) for name in ("pass", "fail", "blocked")
    }
    print(
        json.dumps(
            {
                "phase": args.phase,
                "status": status,
                "reason": reason,
                "counts": counts,
                "owned_asset_count": len(state["assets"]),
                "platform_write_endpoints_called": 0,
                "outbound_unchanged": before is not None and before == after,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0 if status == "completed" else 2


async def bounded_execute(args: argparse.Namespace) -> int:
    # 包括认证与收尾的总时长仍小于十分钟；业务阶段最多540秒。
    async with asyncio.timeout(args.budget_seconds + 10):
        return await execute(args)


def main() -> int:
    args = parse_args()
    try:
        return asyncio.run(bounded_execute(args))
    except Blocked as error:
        print(json.dumps({"status": "blocked", "reason": str(error), "platform_write_endpoints_called": 0}), flush=True)
        return 2
    except Exception as error:
        print(
            json.dumps({"status": "blocked", "reason": type(error).__name__, "platform_write_endpoints_called": 0}),
            flush=True,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
