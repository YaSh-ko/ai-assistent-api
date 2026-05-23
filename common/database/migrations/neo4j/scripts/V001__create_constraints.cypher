// ============================================================================
// V001: Create Constraints
// ============================================================================

// Entry: Дневниковая запись
CREATE CONSTRAINT entry_id_unique IF NOT EXISTS
FOR (e:Entry) REQUIRE e.id IS UNIQUE;

// Concept: Концепт/идея
CREATE CONSTRAINT concept_id_unique IF NOT EXISTS
FOR (c:Concept) REQUIRE c.id IS UNIQUE;

// Affect: Аффект/эмоция
CREATE CONSTRAINT affect_id_unique IF NOT EXISTS
FOR (a:Affect) REQUIRE a.id IS UNIQUE;

// Event: Событие
CREATE CONSTRAINT event_id_unique IF NOT EXISTS
FOR (e:Event) REQUIRE e.id IS UNIQUE;

// Goal: Цель/желание
CREATE CONSTRAINT goal_id_unique IF NOT EXISTS
FOR (g:Goal) REQUIRE g.id IS UNIQUE;

// Experiment: Эксперимент
CREATE CONSTRAINT experiment_id_unique IF NOT EXISTS
FOR (exp:Experiment) REQUIRE exp.id IS UNIQUE;

// Analysis: Анализ
CREATE CONSTRAINT analysis_id_unique IF NOT EXISTS
FOR (a:Analysis) REQUIRE a.id IS UNIQUE;
