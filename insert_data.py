import sqlite3
import json

# Connect to the database
conn = sqlite3.connect('medical_assessment.db')
cursor = conn.cursor()

try:
    # Load data from the JSON file
    with open('curriculum-data/mock-curriculum.json', 'r') as file:
        data = json.load(file)

    # First, let's clear existing data to avoid duplicates
    cursor.execute('DELETE FROM topic_documents')
    cursor.execute('DELETE FROM documents')
    cursor.execute('DELETE FROM competency_teaching_methods')
    cursor.execute('DELETE FROM competency_assessment_methods')
    cursor.execute('DELETE FROM competencies')
    cursor.execute('DELETE FROM topics')
    cursor.execute('DELETE FROM departments')
    cursor.execute('DELETE FROM teaching_methods')
    cursor.execute('DELETE FROM assessment_methods')

    # Insert department
    cursor.execute('INSERT INTO departments (name) VALUES (?)', (data['department'],))
    department_id = cursor.lastrowid

    # Collect unique teaching and assessment methods
    teaching_methods = set()
    assessment_methods = set()
    
    for topic in data['topics']:
        for comp in topic['competencies']:
            teaching_methods.update(comp['teaching_methods'])
            assessment_methods.update(comp['assessment_methods'])

    # Insert teaching methods
    for method in teaching_methods:
        cursor.execute('INSERT INTO teaching_methods (name) VALUES (?)', (method,))

    # Insert assessment methods
    for method in assessment_methods:
        cursor.execute('INSERT INTO assessment_methods (name) VALUES (?)', (method,))

    # Create lookup dictionaries for methods
    cursor.execute('SELECT id, name FROM teaching_methods')
    teaching_method_lookup = {name: id for id, name in cursor.fetchall()}
    
    cursor.execute('SELECT id, name FROM assessment_methods')
    assessment_method_lookup = {name: id for id, name in cursor.fetchall()}

    # Insert topics and competencies
    for topic in data['topics']:
        cursor.execute('INSERT INTO topics (name, department_id) VALUES (?, ?)',
                      (topic['topic'], department_id))
        topic_id = cursor.lastrowid

        for comp in topic['competencies']:
            # Insert competency
            cursor.execute('''
                INSERT INTO competencies (competency_code, description, topic_id)
                VALUES (?, ?, ?)
            ''', (comp['number'], comp['competency'], topic_id))
            competency_id = cursor.lastrowid

            # Insert teaching methods for this competency
            for method in comp['teaching_methods']:
                cursor.execute('''
                    INSERT INTO competency_teaching_methods (competency_id, teaching_method_id)
                    VALUES (?, ?)
                ''', (competency_id, teaching_method_lookup[method]))

            # Insert assessment methods for this competency
            for method in comp['assessment_methods']:
                cursor.execute('''
                    INSERT INTO competency_assessment_methods (competency_id, assessment_method_id)
                    VALUES (?, ?)
                ''', (competency_id, assessment_method_lookup[method]))

    # Commit the changes
    conn.commit()
    print("Data inserted successfully!")

except Exception as e:
    print(f"An error occurred: {e}")
    conn.rollback()

finally:
    conn.close() 