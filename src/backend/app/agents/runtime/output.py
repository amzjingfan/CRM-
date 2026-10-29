"""把模型排版转换为平台可用的纯文本；隐私和事实在转换后独立复核。"""

from markdown_it import MarkdownIt
from markdown_it.token import Token

_MARKDOWN = MarkdownIt("commonmark", {"html": False}).enable(["table", "strikethrough"])


def platform_character_count(text: str) -> int:
    """与前端和平台的 UTF-16 字数约束一致，emoji 计两个单元。"""
    return len(text.encode("utf-16-le")) // 2


def _inline(tokens: list[Token]) -> str:
    parts: list[str] = []
    links: list[tuple[str, int]] = []
    for token in tokens:
        if token.type in {"softbreak", "hardbreak"}:
            parts.append("\n")
        elif token.type == "link_open":
            links.append((str(token.attrGet("href") or ""), len(parts)))
        elif token.type == "link_close" and links:
            href, start = links.pop()
            if href and href != "".join(parts[start:]):
                parts.append(f" ({href})")
        elif token.type == "image":
            parts.append(token.content)
            if token.attrGet("src"):
                parts.append(f" ({token.attrGet('src')})")
        elif token.type in {"text", "code_inline", "html_inline"}:
            parts.append(token.content)
    return "".join(parts)


def plain_text_answer(text: str, *, literal_values: tuple[str, ...] = ()) -> str:
    """按 Markdown 语法移除排版，不用全局替换误删 SKU、算式或正文中的星号。"""
    prefix = "\ue000"
    while prefix in text:
        prefix += "\ue000"
    protected: dict[str, str] = {}
    for value in sorted(set(literal_values), key=lambda item: (-len(item), item)):
        if value and any(char in value for char in "*_`~[]<>") and value in text:
            marker = f"{prefix}{len(protected)}\ue001"
            protected[marker] = value
            text = text.replace(value, marker)
    parts: list[str] = []
    lists: list[tuple[bool, int]] = []

    def newline(count: int) -> None:
        joined = "".join(parts)
        if joined:
            existing = len(joined) - len(joined.rstrip("\n"))
            if existing < count:
                parts.append("\n" * (count - existing))

    for token in _MARKDOWN.parse(text):
        kind = token.type
        if kind == "inline":
            parts.append(_inline(token.children or []))
        elif kind in {"fence", "code_block"}:
            newline(2)
            parts.append(token.content.rstrip("\n"))
            newline(2)
        elif kind in {"bullet_list_open", "ordered_list_open"}:
            newline(1 if lists else 2)
            lists.append((kind == "ordered_list_open", int(token.attrGet("start") or 1)))
        elif kind == "list_item_open":
            newline(1)
            ordered, number = lists[-1]
            parts.append("  " * (len(lists) - 1) + (f"{number}. " if ordered else "• "))
            lists[-1] = (ordered, number + 1)
        elif kind == "list_item_close":
            newline(1)
        elif kind in {"bullet_list_close", "ordered_list_close"}:
            lists.pop()
            newline(1 if lists else 2)
        elif kind in {"heading_close", "blockquote_close"} or (kind == "paragraph_close" and not token.hidden):
            newline(2)
        elif kind in {"th_close", "td_close"}:
            parts.append(" | ")
        elif kind == "tr_close":
            joined = "".join(parts)
            parts[:] = [joined.removesuffix(" | ")]
            newline(1)
        elif kind == "table_close":
            newline(2)
        elif kind == "hr":
            newline(2)
    rendered = "".join(parts).strip()
    for marker, value in protected.items():
        rendered = rendered.replace(marker, value)
    return rendered
