"""商品参数与描述按字段投影和分页，HTML 仅作为数据。"""


def test_product_facts_preserve_attributes_brand_and_description_without_script() -> None:
    from app.agents.tools.arguments import ProductSelectionArguments
    from app.agents.tools.product_facts import product_facts
    from app.workspace.sidebar import SidebarProduct

    product = SidebarProduct(
        id="platform-id",
        title="Training band",
        status="ACTIVATE",
        image_url=None,
        skus=[],
        brand="Demo",
        attributes=[{"name": "Material", "values": ["Latex"]}],
        description_html="<p>Resistance: 20 lb.</p><script>untrustedScript()</script>",
    )
    result = product_facts(product, ProductSelectionArguments(product_ref="p1"))
    assert result["brand"] == "Demo"
    assert result["attributes"][0]["values"] == ["Latex"]
    assert "20 lb." in result["description"]
    assert "untrustedScript" not in str(result) and "platform-id" not in str(result)


def test_long_product_description_is_explicitly_paged_without_losing_text() -> None:
    from app.agents.tools.arguments import ProductSelectionArguments
    from app.agents.tools.product_facts import product_facts
    from app.workspace.sidebar import SidebarProduct

    description = "A" * 3500
    product = SidebarProduct(
        id="platform-id", title="Band", status=None, image_url=None, skus=[], description_html=description
    )
    first = product_facts(product, ProductSelectionArguments(product_ref="p1"))
    second = product_facts(product, ProductSelectionArguments(product_ref="p1", page=2))
    assert first["next_page"] == 2 and second["next_page"] is None
    assert first["description"] + second["description"] == description
