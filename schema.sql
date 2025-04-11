-- First drop all tables in correct order to respect foreign key constraints
DROP TABLE IF EXISTS competency_teaching_methods;
DROP TABLE IF EXISTS competency_assessment_methods;
DROP TABLE IF EXISTS competencies;
DROP TABLE IF EXISTS topics;
DROP TABLE IF EXISTS departments;
DROP TABLE IF EXISTS teaching_methods;
DROP TABLE IF EXISTS assessment_methods;
DROP TABLE IF EXISTS assessments;
DROP TABLE IF EXISTS topic_documents;
DROP TABLE IF EXISTS documents;

-- Then create all tables
CREATE TABLE departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);

CREATE TABLE topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    department_id INTEGER,
    FOREIGN KEY (department_id) REFERENCES departments(id)
);

CREATE TABLE competencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    competency_code TEXT NOT NULL,
    description TEXT NOT NULL,
    topic_id INTEGER,
    FOREIGN KEY (topic_id) REFERENCES topics(id)
);

CREATE TABLE teaching_methods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE assessment_methods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    default_max_marks INTEGER,
    default_passing_marks INTEGER,
    default_duration_minutes INTEGER
);

CREATE TABLE competency_teaching_methods (
    competency_id INTEGER,
    teaching_method_id INTEGER,
    PRIMARY KEY (competency_id, teaching_method_id),
    FOREIGN KEY (competency_id) REFERENCES competencies(id),
    FOREIGN KEY (teaching_method_id) REFERENCES teaching_methods(id)
);

CREATE TABLE competency_assessment_methods (
    competency_id INTEGER,
    assessment_method_id INTEGER,
    PRIMARY KEY (competency_id, assessment_method_id),
    FOREIGN KEY (competency_id) REFERENCES competencies(id),
    FOREIGN KEY (assessment_method_id) REFERENCES assessment_methods(id)
);

-- Assessments table using existing assessment_methods
CREATE TABLE assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    competency_id INTEGER NOT NULL,
    assessment_method_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    max_marks INTEGER,
    passing_marks INTEGER,
    duration_minutes INTEGER,
    url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (competency_id) REFERENCES competencies(id),
    FOREIGN KEY (assessment_method_id) REFERENCES assessment_methods(id)
);

-- Create indexes for better query performance
CREATE INDEX idx_topics_department ON topics(department_id);
CREATE INDEX idx_competencies_topic ON competencies(topic_id);
CREATE INDEX idx_comp_teaching_methods ON competency_teaching_methods(competency_id, teaching_method_id);
CREATE INDEX idx_comp_assessment_methods ON competency_assessment_methods(competency_id, assessment_method_id);
CREATE INDEX idx_assessments_competency ON assessments(competency_id);
CREATE INDEX idx_assessments_method ON assessments(assessment_method_id);

-- Add after the existing tables
CREATE TABLE documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    type TEXT NOT NULL,
    url TEXT NOT NULL,
    description TEXT,
    google_doc_id TEXT UNIQUE,
    google_doc_link TEXT,
    department_id INTEGER,
    status TEXT DEFAULT 'CASE_REVIEW_PENDING' 
        CHECK (status IN (
            'CASE_REVIEW_PENDING',
            'CASE_REVIEW_IN_PROGRESS',
            'CASE_REVIEW_COMPLETE',
            'DATA_REVIEW_IN_PROGRESS',
            'PUBLISHED'
        )),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (department_id) REFERENCES departments(id)
);

CREATE TABLE topic_documents (
    topic_id INTEGER,
    document_id INTEGER,
    PRIMARY KEY (topic_id, document_id),
    FOREIGN KEY (topic_id) REFERENCES topics(id),
    FOREIGN KEY (document_id) REFERENCES documents(id)
);

-- Add indexes for better performance
CREATE INDEX idx_topic_documents ON topic_documents(topic_id);
CREATE INDEX idx_documents_google_id ON documents(google_doc_id);
CREATE INDEX idx_document_department ON topic_documents(document_id);

-- Add index for department lookups
CREATE INDEX idx_documents_department ON documents(department_id);