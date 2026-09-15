\set ON_ERROR_STOP on

-- K2 在现有 PostgreSQL 集群内创建 company_knowledge 独立库，
-- knowledge_migration 拥有 schema；knowledge_runtime 只读权威表并只追加审计。
\getenv migration_password KNOWLEDGE_MIGRATION_PASSWORD
\getenv runtime_password KNOWLEDGE_RUNTIME_PASSWORD

SELECT format('CREATE ROLE knowledge_migration LOGIN PASSWORD %L', :'migration_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'knowledge_migration')
\gexec

SELECT format('CREATE ROLE knowledge_runtime LOGIN PASSWORD %L', :'runtime_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'knowledge_runtime')
\gexec

SELECT 'CREATE DATABASE company_knowledge OWNER knowledge_migration'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'company_knowledge')
\gexec

REVOKE ALL ON DATABASE company_knowledge FROM PUBLIC;
GRANT CONNECT ON DATABASE company_knowledge TO knowledge_runtime;

\connect company_knowledge

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO knowledge_runtime;
REVOKE CREATE ON SCHEMA public FROM knowledge_runtime;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM knowledge_runtime;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO knowledge_runtime;
SELECT 'GRANT INSERT ON TABLE kb_audit_events TO knowledge_runtime'
WHERE to_regclass('public.kb_audit_events') IS NOT NULL
\gexec
ALTER DEFAULT PRIVILEGES FOR ROLE knowledge_migration IN SCHEMA public
REVOKE INSERT, UPDATE, DELETE ON TABLES FROM knowledge_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE knowledge_migration IN SCHEMA public
GRANT SELECT ON TABLES TO knowledge_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE knowledge_migration IN SCHEMA public
REVOKE ALL ON SEQUENCES FROM knowledge_runtime;
