"""已授权工具投影中的客户可见业务编号；不接受原始平台响应。"""

import re

# 只放行固定投影路径，商品 attributes 等自由结构不能借同名字段绕过 DLP。
BUSINESS_IDENTIFIER_PATHS = frozenset(
    {
        ("order_number",),
        ("product_number",),
        ("tracking_number",),
        ("orders", "*", "order_number"),
        ("candidates", "*", "order_number"),
        ("products", "*", "product_number"),
        ("items", "*", "product_number"),
        ("items", "*", "sku_number"),
        ("items", "*", "sku"),
        ("skus", "*", "sku_number"),
        ("skus", "*", "seller_sku"),
        ("packages", "*", "tracking_number"),
        ("events", "*", "tracking_number"),
        ("returns", "*", "return_tracking_number"),
        ("returns", "*", "line_items", "*", "seller_sku"),
    }
)
BUSINESS_IDENTIFIER_FIELDS = frozenset(path[-1] for path in BUSINESS_IDENTIFIER_PATHS)
_IDENTIFIER = re.compile(r"(?=.*[A-Za-z0-9])[A-Za-z0-9._*+/-]{1,200}\Z")


def valid_business_identifier(value: object) -> bool:
    """编号保持原值；拒绝正文、联系方式结构、控制符和超长载荷。"""
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def safe_business_identifier(value: object) -> str | None:
    if value is None:
        return None
    return value if isinstance(value, str) and valid_business_identifier(value) else "[业务标识无效已隐藏]"


def business_identifier_values(facts: object) -> tuple[str, ...]:
    """收集本轮受控投影编号供纯文本格式化保留字面值；不含内部引用。"""
    values: dict[str, None] = {}

    def collect(value: object, path: tuple[str, ...]) -> None:
        if path in BUSINESS_IDENTIFIER_PATHS:
            if isinstance(value, str) and valid_business_identifier(value):
                values[value] = None
        elif isinstance(value, dict):
            for key, item in value.items():
                collect(item, (*path, str(key)))
        elif isinstance(value, list | tuple):
            for item in value:
                collect(item, (*path, "*"))

    collect(facts, ())
    return tuple(values)
