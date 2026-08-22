-- Схема БД-2 (ПРИЁМНИК, target_db) — сюда сервис записывает данные из БД-1.
--
-- Храним «плоскую» выгрузку сотрудников: то, что перенесли из источника,
-- плюс отметку времени переноса. source_employee_id — id из БД-1 (для идемпотентности).
--
-- Применение:
--   psql "postgresql://app:app@localhost:5443/target_db" -f sql/schema_target.sql

DROP TABLE IF EXISTS employee_transfer CASCADE;

CREATE TABLE employee_transfer (
    id                  SERIAL PRIMARY KEY,
    source_employee_id  INTEGER      NOT NULL UNIQUE,   -- id сотрудника в БД-1
    first_name          VARCHAR(100) NOT NULL,
    last_name           VARCHAR(100) NOT NULL,
    email               VARCHAR(255) NOT NULL,
    division_code       VARCHAR(20)  NOT NULL,          -- денормализовано из division.code
    position_title      VARCHAR(200) NOT NULL,          -- денормализовано из position.title
    salary              NUMERIC(12,2) NOT NULL,
    transferred_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX idx_transfer_division ON employee_transfer(division_code);
