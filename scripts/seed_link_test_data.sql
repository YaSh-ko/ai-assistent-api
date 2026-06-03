-- Тестовые наблюдения и цели с life_area (3+3) для проверки связей на графе.
-- Запуск:
--   docker exec -i delez_local_db psql -U postgres -d db_for_delez -f - < scripts/seed_link_test_data.sql
-- Или замените :user_id на свой id из таблицы user.

\set user_id 'ee701b7c-052b-4666-b25d-15bba88ca439'

INSERT INTO entries (id, user_id, title, description, event_date, life_area)
VALUES
  (
    gen_random_uuid(),
    :'user_id',
    'Усталость и меньше спорта',
    'Последние две недели чувствую упадок сил, пропускаю пробежки и зал, настроение ниже обычного.',
    CURRENT_DATE,
    'health'
  ),
  (
    gen_random_uuid(),
    :'user_id',
    'Рост расходов на подписки',
    'Заметил, что траты на доставку еду, подписки и такси выросли примерно на треть по сравнению с прошлым месяцем.',
    CURRENT_DATE,
    'finance'
  ),
  (
    gen_random_uuid(),
    :'user_id',
    'Сложно учиться вечером',
    'После работы тяжело удерживать внимание на курсах по программированию, откладываю домашние задания на выходные.',
    CURRENT_DATE,
    'skills'
  );

INSERT INTO goals (id, user_id, title, description, status, priority, life_area)
VALUES
  (
    gen_random_uuid(),
    :'user_id',
    'Тренировки три раза в неделю',
    'Вернуться к регулярным тренировкам: бег или зал минимум три раза в неделю, отслеживать восстановление.',
    'active',
    'medium',
    'health'
  ),
  (
    gen_random_uuid(),
    :'user_id',
    'Увеличить месячные накопления',
    'Цель — откладывать фиксированную сумму каждый месяц и сократить импульсивные траты на сервисы.',
    'active',
    'medium',
    'finance'
  ),
  (
    gen_random_uuid(),
    :'user_id',
    'Закончить курс по Python',
    'Пройти базовый курс по Python за два месяца с практикой на мини-проектах по вечерам.',
    'active',
    'medium',
    'skills'
  );

SELECT 'entries' AS kind, count(*) FROM entries WHERE user_id = :'user_id' AND life_area IS NOT NULL
UNION ALL
SELECT 'goals', count(*) FROM goals WHERE user_id = :'user_id' AND life_area IS NOT NULL;
