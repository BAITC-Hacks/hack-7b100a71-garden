-- Application-owned data stays outside Supabase's exposed public schema.
-- Connect from the backend as the table owner. Client API roles receive no
-- access; RLS additionally denies rows to non-owner roles without policies.
CREATE SCHEMA IF NOT EXISTS career_quest;
REVOKE ALL ON SCHEMA career_quest FROM PUBLIC;

CREATE TABLE career_quest.dataset_state (
    id integer PRIMARY KEY CHECK (id = 1),
    schema_version integer NOT NULL CHECK (schema_version = 1),
    source_fingerprint text NOT NULL CHECK (length(source_fingerprint) = 64),
    version bigint NOT NULL CHECK (version >= 1),
    dataset_name text NOT NULL CHECK (length(btrim(dataset_name)) > 0),
    dataset_version text NOT NULL CHECK (length(btrim(dataset_version)) > 0),
    as_of_date date NOT NULL
);

CREATE TABLE career_quest.proficiency_scale (
    level integer PRIMARY KEY CHECK (level BETWEEN 0 AND 5),
    description text NOT NULL CHECK (length(btrim(description)) > 0)
);

CREATE TABLE career_quest.skills (
    skill_id text PRIMARY KEY CHECK (length(btrim(skill_id)) > 0),
    position integer NOT NULL CHECK (position >= 0),
    name text NOT NULL CHECK (length(btrim(name)) > 0),
    type text NOT NULL CHECK (type IN ('hard', 'soft')),
    category text NOT NULL CHECK (length(btrim(category)) > 0),
    description text NOT NULL CHECK (length(btrim(description)) > 0)
);

CREATE TABLE career_quest.role_profiles (
    role text NOT NULL CHECK (length(btrim(role)) > 0),
    grade text NOT NULL CHECK (grade IN ('Junior', 'Middle', 'Senior', 'Lead')),
    position integer NOT NULL CHECK (position >= 0),
    PRIMARY KEY (role, grade)
);

CREATE TABLE career_quest.role_required_skills (
    role text NOT NULL,
    grade text NOT NULL,
    skill_id text NOT NULL,
    level integer NOT NULL CHECK (level BETWEEN 0 AND 5),
    position integer NOT NULL CHECK (position >= 0),
    PRIMARY KEY (role, grade, skill_id),
    FOREIGN KEY (role, grade) REFERENCES career_quest.role_profiles (role, grade)
        DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (skill_id) REFERENCES career_quest.skills (skill_id)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE career_quest.role_critical_skills (
    role text NOT NULL,
    grade text NOT NULL,
    skill_id text NOT NULL,
    position integer NOT NULL CHECK (position >= 0),
    PRIMARY KEY (role, grade, skill_id),
    FOREIGN KEY (role, grade, skill_id)
        REFERENCES career_quest.role_required_skills (role, grade, skill_id)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE career_quest.employees (
    employee_id text PRIMARY KEY CHECK (length(btrim(employee_id)) > 0),
    position integer NOT NULL CHECK (position >= 0),
    full_name text NOT NULL CHECK (length(btrim(full_name)) > 0),
    department text NOT NULL CHECK (length(btrim(department)) > 0),
    role text NOT NULL,
    grade text NOT NULL,
    manager_id text,
    hire_date date NOT NULL,
    tenure_months integer NOT NULL CHECK (tenure_months >= 0),
    work_format text NOT NULL CHECK (work_format IN ('office', 'hybrid', 'remote')),
    preferred_language text NOT NULL CHECK (preferred_language IN ('kk', 'ru', 'en')),
    goal_role text,
    goal_grade text,
    last_review_date date NOT NULL,
    CHECK (manager_id IS NULL OR manager_id <> employee_id),
    CHECK ((goal_role IS NULL) = (goal_grade IS NULL)),
    CHECK (last_review_date >= hire_date),
    FOREIGN KEY (role, grade) REFERENCES career_quest.role_profiles (role, grade)
        DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (goal_role, goal_grade) REFERENCES career_quest.role_profiles (role, grade)
        DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (manager_id) REFERENCES career_quest.employees (employee_id)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE career_quest.employee_skills (
    employee_id text NOT NULL,
    skill_id text NOT NULL,
    level integer NOT NULL CHECK (level BETWEEN 0 AND 5),
    position integer NOT NULL CHECK (position >= 0),
    PRIMARY KEY (employee_id, skill_id),
    FOREIGN KEY (employee_id) REFERENCES career_quest.employees (employee_id)
        DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (skill_id) REFERENCES career_quest.skills (skill_id)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE career_quest.events (
    event_id text PRIMARY KEY CHECK (length(btrim(event_id)) > 0),
    position integer NOT NULL CHECK (position >= 0),
    title text NOT NULL CHECK (length(btrim(title)) > 0),
    description text NOT NULL CHECK (length(btrim(description)) > 0),
    type text NOT NULL CHECK (type IN ('compliance', 'onboarding', 'course',
                                      'workshop', 'mentoring', 'certification', 'meetup')),
    format text NOT NULL CHECK (format IN ('online', 'offline', 'self_paced')),
    duration_hours double precision NOT NULL
        CHECK (duration_hours >= 0 AND duration_hours < 'Infinity'::double precision),
    mandatory boolean NOT NULL
);

-- A role can have multiple grade profiles, so target role existence is checked
-- by validate_dataset rather than a foreign key to a non-unique role column.
CREATE TABLE career_quest.event_target_roles (
    event_id text NOT NULL,
    role text NOT NULL CHECK (length(btrim(role)) > 0),
    position integer NOT NULL CHECK (position >= 0),
    PRIMARY KEY (event_id, role),
    FOREIGN KEY (event_id) REFERENCES career_quest.events (event_id)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE career_quest.event_target_grades (
    event_id text NOT NULL,
    grade text NOT NULL CHECK (grade IN ('Junior', 'Middle', 'Senior', 'Lead')),
    position integer NOT NULL CHECK (position >= 0),
    PRIMARY KEY (event_id, grade),
    FOREIGN KEY (event_id) REFERENCES career_quest.events (event_id)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE career_quest.event_gains (
    event_id text NOT NULL,
    skill_id text NOT NULL,
    gain integer NOT NULL CHECK (gain >= 1),
    max_level integer NOT NULL CHECK (max_level BETWEEN 0 AND 5),
    position integer NOT NULL CHECK (position >= 0),
    PRIMARY KEY (event_id, skill_id),
    FOREIGN KEY (event_id) REFERENCES career_quest.events (event_id)
        DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (skill_id) REFERENCES career_quest.skills (skill_id)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE career_quest.event_prerequisites (
    event_id text NOT NULL,
    skill_id text NOT NULL,
    level integer NOT NULL CHECK (level BETWEEN 0 AND 5),
    position integer NOT NULL CHECK (position >= 0),
    PRIMARY KEY (event_id, skill_id),
    FOREIGN KEY (event_id) REFERENCES career_quest.events (event_id)
        DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (skill_id) REFERENCES career_quest.skills (skill_id)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE career_quest.event_sessions (
    event_id text NOT NULL,
    session_date date NOT NULL,
    position integer NOT NULL CHECK (position >= 0),
    PRIMARY KEY (event_id, session_date),
    FOREIGN KEY (event_id) REFERENCES career_quest.events (event_id)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE career_quest.activity_history (
    record_id text PRIMARY KEY CHECK (length(btrim(record_id)) > 0),
    position integer NOT NULL CHECK (position >= 0),
    employee_id text NOT NULL,
    event_id text NOT NULL,
    date date NOT NULL,
    due_date date,
    status text NOT NULL CHECK (status IN ('completed', 'in_progress', 'dropped',
                                          'no_show', 'declined', 'overdue')),
    completion_pct integer NOT NULL CHECK (completion_pct BETWEEN 0 AND 100),
    score integer CHECK (score BETWEEN 0 AND 100),
    feedback_rating integer CHECK (feedback_rating BETWEEN 1 AND 5),
    assigned_by text NOT NULL CHECK (assigned_by IN ('self', 'manager', 'hr')),
    completed_on date,
    CHECK (due_date IS NULL OR due_date >= date),
    CHECK (completed_on IS NULL OR (status = 'completed' AND completed_on >= date)),
    CHECK (score IS NULL OR status = 'completed'),
    CHECK (status <> 'declined' OR assigned_by <> 'self'),
    CHECK (status <> 'overdue' OR due_date IS NOT NULL),
    CHECK ((status = 'completed' AND completion_pct = 100)
        OR (status IN ('in_progress', 'overdue') AND completion_pct <= 95)
        OR (status = 'dropped' AND completion_pct BETWEEN 5 AND 95)
        OR (status IN ('no_show', 'declined') AND completion_pct = 0)),
    FOREIGN KEY (employee_id) REFERENCES career_quest.employees (employee_id)
        DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (event_id) REFERENCES career_quest.events (event_id)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE career_quest.runtime_completions (
    record_id text PRIMARY KEY,
    position bigint NOT NULL CHECK (position >= 0),
    FOREIGN KEY (record_id) REFERENCES career_quest.activity_history (record_id)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE career_quest.idempotency_receipts (
    receipt_key text PRIMARY KEY CHECK (length(btrim(receipt_key)) > 0),
    fingerprint text NOT NULL CHECK (length(btrim(fingerprint)) > 0),
    result jsonb NOT NULL CHECK (jsonb_typeof(result) = 'object')
);

CREATE INDEX employees_manager_idx ON career_quest.employees (manager_id);
CREATE INDEX employees_role_grade_idx ON career_quest.employees (role, grade);
CREATE INDEX activity_employee_date_idx
    ON career_quest.activity_history (employee_id, date, record_id);
CREATE INDEX activity_event_idx ON career_quest.activity_history (event_id);

REVOKE ALL ON ALL TABLES IN SCHEMA career_quest FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA career_quest REVOKE ALL ON TABLES FROM PUBLIC;

-- Supabase projects can inherit grants from earlier settings. In particular,
-- service_role bypasses RLS, so deny schema/table access explicitly as well.
-- Conditional role checks keep this migration usable in ordinary PostgreSQL.
DO $career_quest_permissions$
DECLARE
    client_role text;
BEGIN
    FOR client_role IN
        SELECT rolname FROM pg_catalog.pg_roles
        WHERE rolname IN ('anon', 'authenticated', 'service_role')
    LOOP
        EXECUTE format('REVOKE ALL ON SCHEMA %I FROM %I', 'career_quest', client_role);
        EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA %I FROM %I',
                       'career_quest', client_role);
        EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I REVOKE ALL ON TABLES FROM %I',
                       'career_quest', client_role);
    END LOOP;
END;
$career_quest_permissions$;

ALTER TABLE career_quest.dataset_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE career_quest.proficiency_scale ENABLE ROW LEVEL SECURITY;
ALTER TABLE career_quest.skills ENABLE ROW LEVEL SECURITY;
ALTER TABLE career_quest.role_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE career_quest.role_required_skills ENABLE ROW LEVEL SECURITY;
ALTER TABLE career_quest.role_critical_skills ENABLE ROW LEVEL SECURITY;
ALTER TABLE career_quest.employees ENABLE ROW LEVEL SECURITY;
ALTER TABLE career_quest.employee_skills ENABLE ROW LEVEL SECURITY;
ALTER TABLE career_quest.events ENABLE ROW LEVEL SECURITY;
ALTER TABLE career_quest.event_target_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE career_quest.event_target_grades ENABLE ROW LEVEL SECURITY;
ALTER TABLE career_quest.event_gains ENABLE ROW LEVEL SECURITY;
ALTER TABLE career_quest.event_prerequisites ENABLE ROW LEVEL SECURITY;
ALTER TABLE career_quest.event_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE career_quest.activity_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE career_quest.runtime_completions ENABLE ROW LEVEL SECURITY;
ALTER TABLE career_quest.idempotency_receipts ENABLE ROW LEVEL SECURITY;
