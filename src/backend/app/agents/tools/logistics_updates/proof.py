"""独立复核后持久化低敏发送证明；旧台账缺证据时不得外发。"""

import hashlib
import uuid
from typing import Literal

from pydantic import Field

from .contracts import FrozenModel


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class FileProof(FrozenModel):
    file_id: uuid.UUID
    version_id: uuid.UUID
    version_number: int = Field(ge=1)


class NotificationAuthorization(FrozenModel):
    version: Literal[1] = 1
    review_version: Literal["independent-evidence-privacy-v1"] = "independent-evidence-privacy-v1"
    event_key: str
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy_revision: int = Field(ge=1)
    authorized_by: uuid.UUID
    agent_id: uuid.UUID
    agent_version: int = Field(ge=1)
    prompt_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    file_versions: tuple[FileProof, ...]
    required_permissions: frozenset[str]
