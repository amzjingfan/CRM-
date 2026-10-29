"""商品 HTML 转为不可信纯文本，明示分页而不静默截断规格或参数。"""

import math
from html.parser import HTMLParser

from app.agents.tools.arguments import ProductSelectionArguments
from app.workspace.sidebar import SidebarProduct


class _ProductText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.hidden += 1
        elif tag in {"p", "br", "li", "tr", "div"} and self.parts:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def product_facts(product: SidebarProduct, args: ProductSelectionArguments) -> dict[str, object]:
    parser = _ProductText()
    parser.feed(product.description_html or "")
    text = "".join(parser.parts).strip()
    start = (args.page - 1) * args.page_size
    text_start = (args.page - 1) * 3000
    pages = max(
        math.ceil(len(product.skus) / args.page_size),
        math.ceil(len(product.attributes) / args.page_size),
        math.ceil(len(text) / 3000),
    )
    return {
        "product_ref": args.product_ref,
        "product_number": product.id,
        "title": product.title,
        "status": product.status,
        "brand": product.brand,
        "description": text[text_start : text_start + 3000],
        "attributes": product.attributes[start : start + args.page_size],
        "attribute_count": len(product.attributes),
        "skus": [
            {"sku_number": sku.id, **sku.model_dump(exclude={"id"})}
            for sku in product.skus[start : start + args.page_size]
        ],
        "sku_count": len(product.skus),
        "page": args.page,
        "next_page": args.page + 1 if args.page < pages else None,
    }
