-- Наполнение БД-1 (источник) тестовыми данными.
-- Объёмы кратны 10: 10 подразделений, 10 должностей, 100 сотрудников.
-- Данные детерминированы (генерация по номеру строки) — тесты воспроизводимы.
--
-- Применение:
--   psql "postgresql://app:app@localhost:5442/source_db" -f sql/seed_source.sql

TRUNCATE employee, position, division RESTART IDENTITY CASCADE;

-- 10 подразделений: коды D01..D10
INSERT INTO division (name, code)
SELECT 'Подразделение ' || g,
       'D' || lpad(g::text, 2, '0')
FROM generate_series(1, 10) AS g;

-- 10 должностей: грейд циклично 1..5
INSERT INTO position (title, grade)
SELECT 'Должность ' || g,
       ((g - 1) % 5) + 1
FROM generate_series(1, 10) AS g;

-- 100 сотрудников:
--   division_id  — циклично 1..10
--   position_id  — «разброс» по шагу 7, тоже 1..10
--   salary       — 100000..195000 с шагом 5000
--   hire_date    — от 2020-01-01 с шагом 7 дней
--   is_active    — каждый 10-й неактивен
INSERT INTO employee
    (first_name, last_name, email, division_id, position_id, salary, hire_date, is_active)
SELECT
    'Имя' || g,
    'Фамилия' || g,
    'user' || g || '@example.com',
    ((g - 1) % 10) + 1,
    ((g * 7 - 1) % 10) + 1,
    (100000 + (g % 20) * 5000)::numeric(12,2),
    DATE '2020-01-01' + (g * 7),
    (g % 10 <> 0)
FROM generate_series(1, 100) AS g;
