-- Схема БД-1 (ИСТОЧНИК, source_db) — отсюда сервис читает данные.
--   division 1 --- * employee
--   position 1 --- * employee
--
-- Применение:
--   psql "postgresql://app:app@localhost:5442/source_db" -f sql/schema_source.sql

DROP TABLE IF EXISTS employee CASCADE;
DROP TABLE IF EXISTS position CASCADE;
DROP TABLE IF EXISTS division CASCADE;

CREATE TABLE division (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(200) NOT NULL UNIQUE,
    code        VARCHAR(20)  NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE position (
    id          SERIAL PRIMARY KEY,
    title       VARCHAR(200) NOT NULL UNIQUE,
    grade       INTEGER      NOT NULL DEFAULT 1 CHECK (grade >= 1),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE employee (
    id           SERIAL PRIMARY KEY,
    first_name   VARCHAR(100) NOT NULL,
    last_name    VARCHAR(100) NOT NULL,
    email        VARCHAR(255) NOT NULL UNIQUE,
    division_id  INTEGER      NOT NULL REFERENCES division(id) ON DELETE CASCADE,
    position_id  INTEGER      NOT NULL REFERENCES position(id) ON DELETE RESTRICT,
    salary       NUMERIC(12,2) NOT NULL CHECK (salary > 0),
    hire_date    DATE         NOT NULL,
    is_active    BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX idx_employee_division ON employee(division_id);
CREATE INDEX idx_employee_position ON employee(position_id);
CREATE INDEX idx_employee_active   ON employee(is_active);
