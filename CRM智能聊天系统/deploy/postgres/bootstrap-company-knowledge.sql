\set ON_ERROR_STOP on

-- K2 在现有 PostgreSQL 集群内创建 company_knowledge 独立库，
-- knowledge_migration 拥有 schema，knowledge_runtime 只获得运行时 DML 权限。
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
ALTER DEFAULT PRIVILEGES FOR ROLE knowledge_migration IN SCHEMA public
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO knowledge_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE knowledge_migration IN SCHEMA public
GRANT USAGE, SELECT ON SEQUENCES TO knowledge_runtime;
