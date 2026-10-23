"""通用文档导入的请求配置与策略边界。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DocumentStrategy = Literal[
    "recursive",
    "heading_paragraph",
    "sentence",
    "fixed_token",
    "fixed_char",
    "semantic_similarity",
    "page_slide",
    "ocr_layout",
    "table_rows",
]


class DocumentIndexConfig(BaseModel):
    """与文件版本一同冻结的真实处理参数，不包含未接通的检索设置。"""

    model_config = ConfigDict(extra="forbid")

    strategy: DocumentStrategy = "recursive"
    chunk_size: int = Field(default=500, ge=32, le=10_000)
    overlap: int = Field(default=50, ge=0, le=9_999)
    parser_mode: Literal["auto", "flash", "basic"] = "auto"
    embedding_model: Literal["BAAI/bge-m3"] = "BAAI/bge-m3"

    @model_validator(mode="before")
    @classmethod
    def apply_strategy_defaults(cls, value: object) -> object:
        """字符策略的输入单位不同，未指定大小时使用独立默认。"""
        if isinstance(value, dict) and value.get("strategy") == "fixed_char":
            return {"chunk_size": 1000, "overlap": 100, **value}
        if isinstance(value, dict) and value.get("strategy") == "table_rows":
            return {"overlap": 0, **value}
        return value

    @model_validator(mode="after")
    def validate_window(self) -> "DocumentIndexConfig":
        """重叠不得吞掉全部窗口。"""
        if self.overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP_INVALID")
        return self
