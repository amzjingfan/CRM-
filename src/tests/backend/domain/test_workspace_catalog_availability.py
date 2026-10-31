"""工作台与 Agent 共用的店铺目录只返回可推荐的项目。"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.integrations.tiktok_read import TikTokCoupon, TikTokProduct
from app.workspace import sidebar
from app.workspace.sidebar import SidebarSearch


def product(product_id: str, status: str, quantity: int | None) -> TikTokProduct:
    inventory = [] if quantity is None else [{"quantity": quantity}]
    return TikTokProduct.model_validate(
        {
            "id": product_id,
            "title": f"Product {product_id}",
            "status": status,
            "skus": [{"id": f"sku-{product_id}", "inventory": inventory}],
        }
    )


@pytest.mark.asyncio
async def test_product_search_keeps_only_listed_in_stock_items_and_page_token(monkeypatch: pytest.MonkeyPatch) -> None:
    client = SimpleNamespace(
        search_products=AsyncMock(
            return_value=(
                [
                    product("active", "ACTIVATE", 2),
                    product("sold-out", "ACTIVATE", 0),
                    product("unknown-stock", "ACTIVATE", None),
                    product("inactive", "INACTIVATE", 5),
                ],
                "next-page",
                4,
            )
        )
    )
    monkeypatch.setattr(sidebar, "_tiktok_client", AsyncMock(return_value=client))
    result = await sidebar.search_store_products(
        None, uuid.uuid4(), SidebarSearch(section="products", field="name", query="")
    )
    assert [item.id for item in result.items] == ["active"]
    assert result.next_page_token == "next-page"
    assert result.total_count == 4  # 平台总数，不能冒称过滤后总数。


@pytest.mark.asyncio
async def test_product_id_search_does_not_return_unavailable_item(monkeypatch: pytest.MonkeyPatch) -> None:
    client = SimpleNamespace(get_product=AsyncMock(return_value=product("inactive", "INACTIVATE", 8)))
    monkeypatch.setattr(sidebar, "_tiktok_client", AsyncMock(return_value=client))
    result = await sidebar.search_store_products(
        None, uuid.uuid4(), SidebarSearch(section="products", field="productId", query="inactive")
    )
    assert result.items == []


@pytest.mark.asyncio
async def test_product_detail_rechecks_current_listing_and_stock(monkeypatch: pytest.MonkeyPatch) -> None:
    client = SimpleNamespace(get_product=AsyncMock(return_value=product("sold-out", "ACTIVATE", 0)))
    monkeypatch.setattr(sidebar, "_tiktok_client", AsyncMock(return_value=client))
    with pytest.raises(sidebar.AppError) as error:
        await sidebar.get_store_product(None, uuid.uuid4(), "sold-out")
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_coupon_search_keeps_only_ongoing_claimable_items(monkeypatch: pytest.MonkeyPatch) -> None:
    now = 1_800_000_000
    monkeypatch.setattr(sidebar.time, "time", lambda: now)
    coupons = [
        TikTokCoupon.model_validate({"id": name, "title": name, "status": status, "claim_duration": window})
        for name, status, window in [
            ("active", "ONGOING", {"start_time": now - 10, "end_time": now + 10}),
            ("expired", "ONGOING", {"end_time": now}),
            ("upcoming", "ONGOING", {"start_time": now + 10}),
            ("disabled", "INACTIVE", {}),
        ]
    ]
    client = SimpleNamespace(search_coupons=AsyncMock(return_value=(coupons, "next-page", 4)))
    monkeypatch.setattr(sidebar, "_tiktok_client", AsyncMock(return_value=client))
    result = await sidebar.search_store_coupons(
        None, uuid.uuid4(), SidebarSearch(section="coupons", field="name", query="")
    )
    assert [item.id for item in result.items] == ["active"]
    assert result.next_page_token == "next-page"
    assert result.total_count == 4
