/* All ENUM Datatypes*/

CREATE TYPE storageprovider AS ENUM (
    'minio',
    's3',
    'azure',
    'local'
);

CREATE TYPE tenantstatus AS ENUM (
    'created',
    'active',
    'suspended'
);

CREATE TYPE userstatus AS ENUM (
    'created',
    'active',
    'disabled'
);

CREATE TYPE userrole AS ENUM (
    'admin',
    'user'
);

CREATE TYPE credentialstatus AS ENUM (
    'valid',
    'invalid',
    'revoked'
);

CREATE TYPE languagetype AS ENUM (
    'english'
);

CREATE TYPE documenttype AS ENUM (
    'pdf',
    'docx',
    'doc',
    'markdown',
    'csv',
    'html',
    'image',
    'pptx'
);

CREATE TYPE documentstatus AS ENUM (
    'pending',
    'uploaded',
    'processing',
    'ready',
    'failed',
    'deleted'
);

/* All Table Schema Structures*/
CREATE TABLE IF NOT EXISTS tenant (
    tenant_id UUID PRIMARY KEY,
    organisation VARCHAR(255) NOT NULL,
    status tenantstatus NOT NULL DEFAULT 'created', 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    deleted_by UUID DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenant(tenant_id) ON DELETE CASCADE,
    username VARCHAR(255) NOT NULL,                           
    email VARCHAR(255) NOT NULL UNIQUE,                       
    roles userrole[] NOT NULL DEFAULT '{user}',               
    status userstatus NOT NULL DEFAULT 'created',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    deleted_by UUID DEFAULT NULL                              
);

CREATE TABLE IF NOT EXISTS credentials (
    credentials_id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    provider VARCHAR(255) NOT NULL,
    password_hash TEXT NOT NULL,
    status credentialstatus NOT NULL DEFAULT 'invalid',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    deleted_by UUID DEFAULT NULL,
    password_changed_at TIMESTAMP WITH TIME ZONE DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS document (
    document_id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenant(tenant_id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    mime_type VARCHAR(255) NOT NULL,
    document_type documenttype DEFAULT NULL,
    language languagetype DEFAULT NULL,
    bucket_name TEXT DEFAULT NULL,
    storage_key TEXT NOT NULL,
    storage_provider storageprovider DEFAULT NULL,
    version_id VARCHAR(255) DEFAULT NULL,
    etag VARCHAR(255) DEFAULT NULL,
    checksum VARCHAR(64) DEFAULT NULL,
    size_bytes BIGINT NOT NULL DEFAULT -1,
    status documentstatus NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    deleted_by UUID DEFAULT NULL
);

/* Model Performance Indexes */
CREATE INDEX IF NOT EXISTS idx_tenants_organisation ON tenant(organisation);
CREATE INDEX IF NOT EXISTS idx_tenants_created ON tenant(created_at);

CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_users_created ON users(created_at);

CREATE INDEX IF NOT EXISTS idx_credentials_user ON credentials(user_id);
CREATE INDEX IF NOT EXISTS idx_credentials_created ON credentials(created_at);

CREATE INDEX IF NOT EXISTS idx_documents_tenant_status ON document(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_documents_created ON document(created_at);


/* Seed Default Tenant and User */
INSERT INTO tenant (tenant_id, organisation, status) 
VALUES ('e8b093df-f454-4cae-9080-6078dfebdf19', 'Example Company', 'active')
ON CONFLICT (tenant_id) DO NOTHING;

INSERT INTO users (user_id, tenant_id, username, email, roles, status) 
VALUES ('a3c485fa-3dbb-43d9-9524-ce9f4305df72', 'e8b093df-f454-4cae-9080-6078dfebdf19', 'admin', 'admin@system.local', '{admin,user}', 'active')
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO credentials (credentials_id, user_id, provider, password_hash, status) 
VALUES ('f8e32c0d-c012-4217-ba61-8cf3bb5f2125', 'a3c485fa-3dbb-43d9-9524-ce9f4305df72', 'local', '$2b$12$6KzR8pZ88qB2496mZREvIuGk7yXF5mX5eG7w89z6R2A4e9wI6C2uG', 'valid')
ON CONFLICT (credentials_id) DO NOTHING;