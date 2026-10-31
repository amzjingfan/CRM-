"""动态端口不会放宽测试数据库的主机、账号和库名隔离。"""

import pytest
from _support import require_isolated_postgres_url


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://crm_test:crm_test@localhost:5433/crm_test",
        "postgresql+asyncpg://crm_test:crm_test@127.0.0.1:56875/crm_test",
        "postgresql+asyncpg://crm_test:crm_test@127.0.0.1:56874/crm_template_batch_full_test_20261030",
    ],
)
def test_explicit_isolated_database_supports_independent_ports(url):
    assert require_isolated_postgres_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        None,
        "postgresql+asyncpg://crm_test:crm_test@localhost:56875/crm_test?host=remote.example",
        "postgresql+asyncpg://crm_test:crm_test@localhost:56875/crm_test?user=crm&database=crm",
        "postgresql+asyncpg://crm_test:crm_test@localhost:56875/crm_test?host=localhost&host=remote.example",
        "postgresql+asyncpg://crm_test:crm_test@remote.example:56875/crm_test",
        "postgresql+asyncpg://crm:crm_test@localhost:56875/crm_test",
        "postgresql+asyncpg://crm_test:crm_test@localhost:56875/crm",
        "postgresql+asyncpg://crm_test:wrong@localhost:56875/crm_test",
        "postgresql://crm_test:crm_test@localhost:56875/crm_test",
    ],
)
def test_business_or_remote_database_is_rejected(url):
    with pytest.raises(AssertionError):
        require_isolated_postgres_url(url)
