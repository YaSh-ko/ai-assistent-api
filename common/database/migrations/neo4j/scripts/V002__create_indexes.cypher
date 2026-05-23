// ============================================================================
// V002: Create Indexes
// ============================================================================

// Entry indexes
CREATE INDEX entry_user_id IF NOT EXISTS
FOR (e:Entry) ON (e.user_id);

CREATE INDEX entry_timestamp IF NOT EXISTS
FOR (e:Entry) ON (e.timestamp);

CREATE INDEX entry_session_id IF NOT EXISTS
FOR (e:Entry) ON (e.session_id);

// Concept indexes
CREATE INDEX concept_name IF NOT EXISTS
FOR (c:Concept) ON (c.name);

CREATE INDEX concept_user_id IF NOT EXISTS
FOR (c:Concept) ON (c.user_id);

// Affect indexes
CREATE INDEX affect_name IF NOT EXISTS
FOR (a:Affect) ON (a.name);

CREATE INDEX affect_user_id IF NOT EXISTS
FOR (a:Affect) ON (a.user_id);

// Event indexes
CREATE INDEX event_user_id IF NOT EXISTS
FOR (e:Event) ON (e.user_id);

CREATE INDEX event_date IF NOT EXISTS
FOR (e:Event) ON (e.date);

// Goal indexes
CREATE INDEX goal_title IF NOT EXISTS
FOR (g:Goal) ON (g.title);

CREATE INDEX goal_user_id IF NOT EXISTS
FOR (g:Goal) ON (g.user_id);

CREATE INDEX goal_created_at IF NOT EXISTS
FOR (g:Goal) ON (g.created_at);

CREATE INDEX goal_status IF NOT EXISTS
FOR (g:Goal) ON (g.status);

// Experiment indexes
CREATE INDEX experiment_title IF NOT EXISTS
FOR (exp:Experiment) ON (exp.title);

CREATE INDEX experiment_user_id IF NOT EXISTS
FOR (exp:Experiment) ON (exp.user_id);

CREATE INDEX experiment_started_at IF NOT EXISTS
FOR (exp:Experiment) ON (exp.started_at);

CREATE INDEX experiment_status IF NOT EXISTS
FOR (exp:Experiment) ON (exp.status);

// Analysis indexes
CREATE INDEX analysis_title IF NOT EXISTS
FOR (a:Analysis) ON (a.title);

CREATE INDEX analysis_user_id IF NOT EXISTS
FOR (a:Analysis) ON (a.user_id);

CREATE INDEX analysis_analyzed_at IF NOT EXISTS
FOR (a:Analysis) ON (a.analyzed_at);
