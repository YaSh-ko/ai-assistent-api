// ============================================================================
// V003: Seed Test Data
// ============================================================================

// Создать тестового пользователя
CREATE (u:User {
  id: 'test_user_001',
  username: 'test_user',
  created_at: datetime()
});

// Создать тестовую запись Entry
CREATE (e1:Entry {
  id: 'entry_001',
  user_id: 'test_user_001',
  session_id: 'session_001',
  timestamp: datetime('2024-11-25T10:00:00'),
  content: 'Сегодня я осознал, что прокрастинация — это не лень, а защитный механизм от страха неудачи.',
  content_summary: 'Размышление о природе прокрастинации',
  word_count: 15,
  sentiment_score: 0.3,
  created_at: datetime(),
  updated_at: datetime()
});

// Создать концепт
CREATE (c1:Concept {
  id: 'concept_001',
  name: 'прокрастинация как защита',
  description: 'Прокрастинация — это защитный механизм психики от страха неудачи',
  relevance: 0.9,
  user_id: 'test_user_001',
  created_at: datetime(),
  updated_at: datetime()
});

// Создать аффект
CREATE (a1:Affect {
  id: 'affect_001',
  name: 'тревога',
  user_id: 'test_user_001',
  valence: -0.6,
  arousal: 0.7,
  description: 'Ощущение беспокойства и напряжения',
  created_at: datetime(),
  updated_at: datetime()
});

// Создать событие
CREATE (ev1:Event {
  id: 'event_001',
  title: 'дедлайн проекта',
  user_id: 'test_user_001',
  date: datetime('2024-11-30T23:59:59'),
  importance: 0.9,
  created_at: datetime(),
  updated_at: datetime()
});

// Создать цель
CREATE (g1:Goal {
  id: 'goal_001',
  title: 'Научиться работать со страхом неудачи',
  description: 'Разработать стратегии работы со страхом вместо избегания',
  status: 'active',
  priority: 'high',
  created_at: datetime(),
  target_date: datetime('2025-01-01T00:00:00'),
  user_id: 'test_user_001',
  updated_at: datetime()
});

// Создать связи
MATCH (e:Entry {id: 'entry_001'}), (c:Concept {id: 'concept_001'})
CREATE (e)-[:MENTIONS {
  context: 'прокрастинация — это не лень, а защитный механизм',
  relevance: 0.95,
  mentioned_at: datetime()
}]->(c);

MATCH (e:Entry {id: 'entry_001'}), (a:Affect {id: 'affect_001'})
CREATE (e)-[:EXPRESSES {
  intensity: 0.7,
  context: 'чувствую тревогу перед дедлайном',
  expressed_at: datetime()
}]->(a);

MATCH (e:Entry {id: 'entry_001'}), (ev:Event {id: 'event_001'})
CREATE (e)-[:DESCRIBES {
  sentiment: -0.3,
  perspective: 'present',
  context: 'приближается дедлайн проекта'
}]->(ev);

MATCH (e:Entry {id: 'entry_001'}), (g:Goal {id: 'goal_001'})
CREATE (e)-[:RELATES_TO {
  relation_type: 'reflection',
  sentiment: 0.4,
  context: 'осознал связь между страхом и прокрастинацией'
}]->(g);
