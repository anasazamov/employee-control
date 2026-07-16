"""Boshlang'ich sxema: barcha jadvallar + RLS + hypertable + append-only grantlar.

Reja (docs/PLAN.md §4–5) bo'yicha:
- shared-schema tenancy: har tenant-jadvalda org_id + RLS (ENABLE + FORCE);
- app_user roli BYPASSRLS'siz — GUC (app.org_id) o'rnatilmagan tranzaksiyada 0 qator;
- checkins / location_points / audit_log / access_log — app_user uchun append-only;
- location_points — TimescaleDB hypertable (1 kunlik chunk, siqish 7 kundan keyin,
  xom ma'lumot 90 kun retention).

Revision ID: 0001
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# RLS o'rnatiladigan tenant-jadvallar (organizations/invites/otp_codes EMAS — auth/platforma-plane)
TENANT_TABLES = [
    "departments",
    "users",
    "user_scope_grants",
    "devices",
    "shifts",
    "site_types",
    "sites",
    "assignments",
    "site_presence",
    "checkins",
    "face_embeddings",
    "location_points",
    "audit_log",
    "access_log",
    "consents",
]

# Append-only: dalil-jadvallar — app_user'ga UPDATE/DELETE berilmaydi
APPEND_ONLY_TABLES = ["checkins", "location_points", "audit_log", "access_log"]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS ltree")
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    # Runtime-rol (dev-parol; prod'da deploy-skript ALTER ROLE bilan almashtiradi)
    op.execute(
        """
        DO $$ BEGIN
          IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
            CREATE ROLE app_user LOGIN PASSWORD 'app_password';
          END IF;
        END $$;
        """
    )

    # --- Platforma / auth-plane jadvallar (RLS'siz) ---
    op.execute(
        """
        CREATE TABLE organizations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            slug varchar(64) NOT NULL UNIQUE,
            name varchar(255) NOT NULL,
            status varchar(16) NOT NULL DEFAULT 'active',
            plan varchar(32) NOT NULL DEFAULT 'trial',
            limits jsonb NOT NULL DEFAULT '{}',
            settings jsonb NOT NULL DEFAULT '{}',
            kms_key_id varchar(255),
            ltree_root varchar(64) NOT NULL UNIQUE,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )

    # --- Tenant-jadvallar ---
    op.execute(
        """
        CREATE TABLE departments (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            name varchar(255) NOT NULL,
            path ltree NOT NULL UNIQUE,
            head_user_id uuid,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_departments_org_id ON departments (org_id);
        CREATE INDEX ix_departments_path_gist ON departments USING gist (path);
        """
    )
    op.execute(
        """
        CREATE TABLE users (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            department_id uuid REFERENCES departments(id) ON DELETE SET NULL,
            role varchar(16) NOT NULL DEFAULT 'field_employee',
            full_name varchar(255) NOT NULL,
            phone varchar(20) NOT NULL,
            employee_no varchar(64),
            status varchar(16) NOT NULL DEFAULT 'active',
            attributes jsonb NOT NULL DEFAULT '{}',
            face_enrolled_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_users_org_phone UNIQUE (org_id, phone),
            CONSTRAINT ck_users_role CHECK
                (role IN ('org_admin','hr','dept_head','field_employee'))
        );
        CREATE INDEX ix_users_org_id ON users (org_id);
        ALTER TABLE departments
            ADD CONSTRAINT fk_departments_head_user
            FOREIGN KEY (head_user_id) REFERENCES users(id) ON DELETE SET NULL;
        """
    )
    op.execute(
        """
        CREATE TABLE user_scope_grants (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            department_path ltree NOT NULL,
            granted_by uuid REFERENCES users(id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_scope_grant UNIQUE (user_id, department_path)
        );
        CREATE INDEX ix_user_scope_grants_org_id ON user_scope_grants (org_id);
        """
    )
    op.execute(
        """
        CREATE TABLE devices (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            platform varchar(16) NOT NULL,
            model varchar(128),
            fingerprint varchar(128) NOT NULL,
            pubkey text,
            push_token text,
            status varchar(16) NOT NULL DEFAULT 'active',
            bound_at timestamptz NOT NULL DEFAULT now(),
            last_seen_at timestamptz
        );
        CREATE INDEX ix_devices_org_id ON devices (org_id);
        -- 1 faol qurilma / (org, xodim) — reja §7.5
        CREATE UNIQUE INDEX uq_devices_active_per_user
            ON devices (org_id, user_id) WHERE status = 'active';
        """
    )
    op.execute(
        """
        CREATE TABLE shifts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            starts_at timestamptz NOT NULL,
            ends_at timestamptz NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_shifts_org_id ON shifts (org_id);
        CREATE INDEX ix_shifts_user_id ON shifts (user_id);
        """
    )
    op.execute(
        """
        CREATE TABLE site_types (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            name varchar(128) NOT NULL,
            icon varchar(64),
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_site_types_org_id ON site_types (org_id);
        """
    )
    op.execute(
        """
        CREATE TABLE sites (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            site_type_id uuid REFERENCES site_types(id) ON DELETE SET NULL,
            name varchar(255) NOT NULL,
            address text,
            geom geometry(Polygon, 4326),
            center geography(Point, 4326) NOT NULL,
            radius_m integer NOT NULL DEFAULT 150,
            min_dwell_minutes integer NOT NULL DEFAULT 15,
            status varchar(16) NOT NULL DEFAULT 'active',
            attributes jsonb NOT NULL DEFAULT '{}',
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_sites_org_id ON sites (org_id);
        CREATE INDEX ix_sites_center_gist ON sites USING gist (center);
        CREATE INDEX ix_sites_geom_gist ON sites USING gist (geom);
        """
    )
    op.execute(
        """
        CREATE TABLE assignments (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            site_id uuid NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
            employee_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            assigned_by uuid REFERENCES users(id) ON DELETE SET NULL,
            due_from timestamptz,
            due_to timestamptz,
            reveal_at timestamptz,
            status varchar(16) NOT NULL DEFAULT 'pending',
            min_dwell_minutes integer,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_assignments_org_id ON assignments (org_id);
        """
    )
    op.execute(
        """
        CREATE TABLE site_presence (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            site_id uuid NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
            entered_at timestamptz NOT NULL,
            exited_at timestamptz,
            dwell_seconds integer
        );
        CREATE INDEX ix_site_presence_org_id ON site_presence (org_id);
        CREATE INDEX ix_site_presence_user_id ON site_presence (user_id);
        CREATE INDEX ix_site_presence_site_id ON site_presence (site_id);
        -- "hozir ichkarida" tez so'rovi uchun
        CREATE INDEX ix_site_presence_open
            ON site_presence (org_id, site_id) WHERE exited_at IS NULL;
        """
    )
    op.execute(
        """
        CREATE TABLE checkins (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            assignment_id uuid REFERENCES assignments(id) ON DELETE SET NULL,
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            device_id uuid REFERENCES devices(id) ON DELETE SET NULL,
            site_id uuid REFERENCES sites(id) ON DELETE SET NULL,
            ts timestamptz NOT NULL,
            lat double precision NOT NULL,
            lon double precision NOT NULL,
            accuracy_m real,
            inside_geofence boolean,
            selfie_key text,
            comment text,
            ondevice_score real,
            server_face_score real,
            server_spoof_score real,
            device_integrity jsonb NOT NULL DEFAULT '{}',
            verdict varchar(16) NOT NULL DEFAULT 'pending',
            verdict_reasons varchar(64)[],
            reviewed_by uuid REFERENCES users(id) ON DELETE SET NULL,
            reviewed_at timestamptz,
            row_hash bytea,
            prev_hash bytea,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_checkins_verdict CHECK
                (verdict IN ('pending','verified','flagged','rejected'))
        );
        CREATE INDEX ix_checkins_org_id ON checkins (org_id);
        CREATE INDEX ix_checkins_user_id ON checkins (user_id);
        CREATE INDEX ix_checkins_site_id ON checkins (site_id);
        """
    )
    op.execute(
        """
        CREATE TABLE face_embeddings (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            embedding vector(512) NOT NULL,
            source varchar(32) NOT NULL DEFAULT 'enrollment',
            quality real,
            model_ver varchar(64) NOT NULL,
            active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        -- 1:N skan HAR DOIM org-filtrli (reja §4); ANN indeks ataylab YO'Q
        CREATE INDEX ix_face_embeddings_org_id ON face_embeddings (org_id);
        CREATE INDEX ix_face_embeddings_user_id ON face_embeddings (user_id);
        """
    )
    op.execute(
        """
        CREATE TABLE location_points (
            ts timestamptz NOT NULL,
            point_uuid uuid NOT NULL,
            org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            user_id uuid NOT NULL,
            device_id uuid,
            geog geography(Point, 4326) NOT NULL,
            accuracy_m real,
            speed_mps real,
            heading real,
            battery smallint,
            is_mock boolean NOT NULL DEFAULT false,
            provider varchar(32),
            PRIMARY KEY (ts, point_uuid)
        );
        """
    )
    op.execute(
        """
        SELECT create_hypertable('location_points', 'ts',
                                 chunk_time_interval => INTERVAL '1 day');
        """
    )
    op.execute(
        """
        CREATE INDEX ix_location_points_org_user_ts
            ON location_points (org_id, user_id, ts DESC);
        CREATE INDEX ix_location_points_geog_gist ON location_points USING gist (geog);
        """
    )
    # DIQQAT: TimescaleDB columnstore (siqish) va RLS bitta hypertable'da birga
    # ishlamaydi. Izolyatsiya (RLS) xavfsizlik-kritik, shuning uchun siqish
    # keyinga qoldirildi — variantlar: eski chunk'larni alohida siqilgan
    # arxiv-jadvalga ko'chirish yoki Timescale RLS+columnstore qo'llab-quvvatlaganda
    # yoqish. Retention (chunk drop) RLS bilan muammosiz ishlaydi.
    op.execute(
        """
        -- Xom nuqtalar 90 kun (reja §15 retention); 5-daqiqalik continuous aggregate
        -- keyingi migratsiyada (tranzaksiyadan tashqarida yaratilishi kerak).
        SELECT add_retention_policy('location_points', INTERVAL '90 days');
        """
    )
    op.execute(
        """
        CREATE TABLE audit_log (
            id bigserial PRIMARY KEY,
            org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            ts timestamptz NOT NULL DEFAULT now(),
            actor_id uuid,
            action varchar(64) NOT NULL,
            object_type varchar(64),
            object_id uuid,
            detail jsonb NOT NULL DEFAULT '{}',
            ip inet,
            row_hash bytea,
            prev_hash bytea
        );
        CREATE INDEX ix_audit_log_org_id ON audit_log (org_id);
        """
    )
    op.execute(
        """
        CREATE TABLE access_log (
            id bigserial PRIMARY KEY,
            org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            ts timestamptz NOT NULL DEFAULT now(),
            viewer_id uuid NOT NULL,
            subject_id uuid,
            resource varchar(64) NOT NULL,
            detail jsonb NOT NULL DEFAULT '{}'
        );
        CREATE INDEX ix_access_log_org_id ON access_log (org_id);
        """
    )
    op.execute(
        """
        CREATE TABLE consents (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            template_version varchar(32) NOT NULL,
            signed_at timestamptz NOT NULL DEFAULT now(),
            withdrawn_at timestamptz
        );
        CREATE INDEX ix_consents_org_id ON consents (org_id);
        CREATE INDEX ix_consents_user_id ON consents (user_id);
        """
    )

    # --- Auth-plane jadvallar (RLS'siz — token org-kontekstsiz topilishi kerak) ---
    op.execute(
        """
        CREATE TABLE invites (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            employee_id uuid REFERENCES users(id) ON DELETE CASCADE,
            token_hash varchar(64) NOT NULL UNIQUE,
            code varchar(8) NOT NULL,
            expires_at timestamptz NOT NULL,
            used_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE otp_codes (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            phone varchar(20) NOT NULL,
            code_hash varchar(64) NOT NULL,
            purpose varchar(32) NOT NULL DEFAULT 'activation',
            expires_at timestamptz NOT NULL,
            consumed_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_otp_codes_phone ON otp_codes (phone);
        """
    )

    # --- RLS: ENABLE + FORCE + org-izolyatsiya siyosati ---
    # current_setting(..., true): GUC o'rnatilmagan bo'lsa NULL → policy false → 0 qator.
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY org_isolation ON {table}
                USING (org_id = current_setting('app.org_id', true)::uuid)
                WITH CHECK (org_id = current_setting('app.org_id', true)::uuid)
            """
        )

    # --- Grantlar: app_user (runtime-rol) ---
    op.execute("GRANT USAGE ON SCHEMA public TO app_user")
    op.execute("GRANT SELECT ON organizations TO app_user")
    op.execute("GRANT SELECT, INSERT, UPDATE ON invites, otp_codes TO app_user")
    for table in TENANT_TABLES:
        if table in APPEND_ONLY_TABLES:
            # Dalil-jadvallar: faqat SELECT + INSERT. Tuzatish = kompensatsion yozuv.
            op.execute(f"GRANT SELECT, INSERT ON {table} TO app_user")
        else:
            op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user")
    op.execute("GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO app_user")


def downgrade() -> None:
    for table in [
        "otp_codes",
        "invites",
        "consents",
        "access_log",
        "audit_log",
        "location_points",
        "face_embeddings",
        "checkins",
        "site_presence",
        "assignments",
        "sites",
        "site_types",
        "shifts",
        "devices",
        "user_scope_grants",
        "users",
        "departments",
        "organizations",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
