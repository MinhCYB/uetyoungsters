"""Small idempotent migrations for deployments created before Alembic adoption."""
from sqlalchemy import text
from sqlalchemy.engine import Engine


ASSESSMENT_DRAFT_MIGRATIONS = (
    # Ownership was introduced after the first assessment table was deployed.
    # Keep user_id nullable at database level so an anonymous legacy attempt can
    # survive the migration; all new attempts are created with an authenticated
    # user by the application service.
    "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS user_id VARCHAR(36) NULL",
    "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(36) NULL",
    "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS last_saved_at TIMESTAMP WITH TIME ZONE NULL",
    "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS current_question_id VARCHAR(120) NULL",
    "ALTER TABLE assessment_answers ADD COLUMN IF NOT EXISTS score DOUBLE PRECISION NULL",
    "ALTER TABLE assessment_answers ADD COLUMN IF NOT EXISTS ai_feedback TEXT NULL",
    "CREATE INDEX IF NOT EXISTS ix_assessments_user_id ON assessments (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_assessments_tenant_id ON assessments (tenant_id)",
    """DO $$ BEGIN
       IF NOT EXISTS (
         SELECT 1 FROM pg_constraint WHERE conname = 'assessments_user_id_fkey'
       ) THEN
         ALTER TABLE assessments
         ADD CONSTRAINT assessments_user_id_fkey
         FOREIGN KEY (user_id) REFERENCES users(id);
       END IF;
       END $$""",
    "ALTER TABLE invitations ADD COLUMN IF NOT EXISTS profile_type VARCHAR(30) NULL",
    "ALTER TABLE candidate_profiles ADD COLUMN IF NOT EXISTS student_code VARCHAR(80) NULL",
)

CANDIDATE_PROFILE_BACKFILL = (
    """DO $$ BEGIN
       IF to_regclass('public.student_profiles') IS NOT NULL THEN
         INSERT INTO candidate_profiles
           (id, user_id, tenant_id, class_id, profile_type, student_code, basic_information, version, created_at, updated_at)
         SELECT sp.id, sp.user_id, sp.tenant_id, sp.class_id, sp.profile_type, sp.student_code,
                COALESCE(sp.basic_information, '{}'::json), 1, NOW(), NOW()
         FROM student_profiles sp ON CONFLICT (user_id) DO UPDATE
         SET student_code = COALESCE(candidate_profiles.student_code, EXCLUDED.student_code);
       END IF;
       END $$""",
    """DO $$ BEGIN
       IF to_regclass('public.professional_profiles') IS NOT NULL THEN
         INSERT INTO candidate_profiles
           (id, user_id, tenant_id, class_id, profile_type, current_career_id, basic_information,
            version, created_at, updated_at)
         SELECT pp.id, pp.user_id, u.tenant_id, NULL, 'PROFESSIONAL', pp.current_career_id,
                COALESCE(pp.parsed_data, '{}'::json), 1, pp.created_at, pp.updated_at
         FROM professional_profiles pp JOIN users u ON u.id = pp.user_id
         ON CONFLICT (user_id) DO NOTHING;
       END IF;
       END $$""",
    """INSERT INTO candidate_profiles
       (id, user_id, tenant_id, class_id, profile_type, basic_information, version, created_at, updated_at)
       SELECT u.id, u.id, u.tenant_id, NULL, 'PROFESSIONAL', '{}'::json, 1, u.created_at, u.updated_at
       FROM users u
       WHERE u.role = 'PROFESSIONAL'
       ON CONFLICT (user_id) DO NOTHING""",
)

ACADEMIC_RECORD_MIGRATIONS = (
    "ALTER TABLE academic_records ADD COLUMN IF NOT EXISTS candidate_profile_id VARCHAR(36) NULL",
    """DO $$
       BEGIN
         IF EXISTS (
           SELECT 1 FROM information_schema.columns
           WHERE table_name = 'academic_records' AND column_name = 'student_profile_id'
         ) THEN
           UPDATE academic_records ar
           SET candidate_profile_id = cp.id
           FROM student_profiles sp
           JOIN candidate_profiles cp ON cp.user_id = sp.user_id
           WHERE ar.student_profile_id = sp.id AND ar.candidate_profile_id IS NULL;
           IF EXISTS (SELECT 1 FROM academic_records WHERE candidate_profile_id IS NULL) THEN
             RAISE EXCEPTION 'Cannot migrate academic_records: orphan student_profile_id found';
           END IF;
           ALTER TABLE academic_records DROP COLUMN student_profile_id;
         END IF;
       END $$""",
    """DO $$
       BEGIN
         IF NOT EXISTS (
           SELECT 1 FROM pg_constraint WHERE conname = 'academic_records_candidate_profile_id_fkey'
         ) THEN
           ALTER TABLE academic_records
           ADD CONSTRAINT academic_records_candidate_profile_id_fkey
           FOREIGN KEY (candidate_profile_id) REFERENCES candidate_profiles(id);
         END IF;
       END $$""",
    "ALTER TABLE academic_records ALTER COLUMN candidate_profile_id SET NOT NULL",
    "CREATE INDEX IF NOT EXISTS ix_academic_records_candidate_profile_id ON academic_records (candidate_profile_id)",
)

DOCUMENT_MIGRATIONS = (
    """DO $$
       BEGIN
         IF to_regclass('public.cv_documents') IS NOT NULL THEN
           INSERT INTO profile_documents
             (id, candidate_profile_id, document_type, original_filename, object_key,
              extraction_status, structured_data, uploaded_at, updated_at)
           SELECT cv.id, cp.id, 'CV', cv.object_key, cv.object_key,
                  cv.parse_status, '{}'::json, cv.uploaded_at, cv.uploaded_at
           FROM cv_documents cv
           JOIN professional_profiles pp ON pp.id = cv.professional_profile_id
           JOIN candidate_profiles cp ON cp.user_id = pp.user_id
           ON CONFLICT (id) DO NOTHING;
           DROP TABLE cv_documents;
         END IF;
       END $$""",
)

def run_migrations(engine: Engine) -> None:
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as connection:
        for statement in (
            *ASSESSMENT_DRAFT_MIGRATIONS,
            *CANDIDATE_PROFILE_BACKFILL,
            *ACADEMIC_RECORD_MIGRATIONS,
            *DOCUMENT_MIGRATIONS,
        ):
            connection.execute(text(statement))
