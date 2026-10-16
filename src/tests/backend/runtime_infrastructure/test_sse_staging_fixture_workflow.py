"""G5 staging 工作流将只读核对与 50 账号写入分开。"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]
WORKFLOW = ROOT / ".github/workflows/prepare-staging-sse-fixture.yml"


def test_dispatch_is_staging_only_and_write_requires_separate_confirmation() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    dispatch = workflow[True]["workflow_dispatch"]["inputs"]
    assert dispatch["mode"]["options"] == ["check_only", "provision", "preflight", "diagnose_auth"]
    assert dispatch["expected_source_sha"]["required"] is True
    assert dispatch["expected_backend_image"]["required"] is True
    assert workflow["permissions"] == {"contents": "read"}
    job = workflow["jobs"]["prepare"]
    assert job["runs-on"] == ["self-hosted", "linux", "x64", "crm-staging"]
    assert job["environment"] == "staging"
    steps = {step["name"]: step for step in job["steps"]}
    source = steps["Verify reviewed source"]["run"]
    runtime = steps["Check staging runtime"]["run"]
    readonly = steps["Read-only fixture check"]["run"]
    provision = steps["Provision exact fixture"]["run"]
    preflight = steps["Preflight 50 identities and sessions"]["run"]
    diagnostic = steps["Diagnose one existing G5 token"]["run"]
    assert "EXPECTED_SOURCE_SHA -cne $env:GITHUB_SHA" in source
    assert "git/commits/$env:GITHUB_SHA" in source
    assert "blobSha" in source
    assert "Config.Image" in runtime
    assert "CRM_STAGING_ENV_FILE" in runtime
    assert "database_sha256" in runtime
    assert "Get-ChildItem -LiteralPath $privateDir -Force" in runtime
    assert "Existing G5 private material requires reconciliation" in runtime
    assert "g5-38852775454-1.json" in runtime
    assert "'diagnose_auth'" in runtime
    assert "type=bind,source=$hostFile,target=/opt/crm-g5-credentials.json,readonly" in preflight
    assert "scripts.preflight_sse_staging_fixture" in preflight
    assert "chat_query_limit" in preflight
    assert "access_token_expire_minutes" in preflight
    assert "--env-file" not in preflight
    assert "--execute" not in preflight
    assert "load_test_sse" not in preflight
    assert "if ($exitCode -ne 0 -or $report.ready -cne $true -or $limit -lt 50)" in preflight
    assert steps["Read-only fixture check"]["if"] == "inputs.mode == 'check_only' || inputs.mode == 'provision'"
    assert steps["Preflight 50 identities and sessions"]["if"] == "inputs.mode == 'preflight'"
    assert steps["Diagnose one existing G5 token"]["if"] == "inputs.mode == 'diagnose_auth'"
    assert "scripts.diagnose_sse_staging_auth" in diagnostic
    assert "EXPECTED_RUNTIME_JWT_SHA256" in diagnostic
    assert "EXPECTED_RUNTIME_JWT_ALGORITHM" in diagnostic
    assert "--env-file" in diagnostic
    assert "--read-only" in diagnostic
    assert "--execute" not in diagnostic
    assert "load_test_sse" not in diagnostic
    assert "Write-Output $output" not in diagnostic
    assert "provider_calls=0" in diagnostic
    assert '"env_file=$envFile"' not in runtime
    assert steps["Read-only fixture check"]["env"]["ENV_FILE"] == "${{ secrets.CRM_STAGING_ENV_FILE }}"
    assert steps["Provision exact fixture"]["env"]["ENV_FILE"] == "${{ secrets.CRM_STAGING_ENV_FILE }}"
    assert list(steps).index("Read-only fixture check") < list(steps).index("Provision exact fixture")
    assert "check_sse_staging_fixture" in readonly
    assert "--execute" not in readonly
    assert "Write-Output $output" not in readonly
    assert "failure_stage=$($Matches[1])" in readonly
    assert steps["Provision exact fixture"]["if"] == "inputs.mode == 'provision'"
    assert "create-50-isolated-staging-users" in provision
    assert "--execute" in provision
    assert "prepare_sse_staging_fixture" in provision
    assert "PYTHONPATH=/opt/crm-g5-source:/app" in provision
    assert "type=bind,source=$source,target=/opt/crm-g5-source,readonly" in provision
    assert "type=bind,source=$env:PRIVATE_DIR,target=/opt/crm-g5-credentials" in provision
    assert "--mount" in provision
    assert "--rm" in provision
    assert "LLM_ENABLED=true" not in provision
