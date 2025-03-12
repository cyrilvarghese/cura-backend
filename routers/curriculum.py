from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
import sqlite3
from pydantic import BaseModel

router = APIRouter(
    prefix="/curriculum",
    tags=["curriculum"],
    responses={404: {"description": "Not found"}},
)

class AssessmentBriefModel(BaseModel):
    id: int
    title: str

class CompetencyModel(BaseModel):
    competency_code: str
    competency: str
    teaching_methods: List[str]
    assessments: List[AssessmentBriefModel] = []  # Made optional with default empty list
    assessment_methods: Optional[List[str]] = None  # Added to match incoming data

class DocumentModel(BaseModel):
    id: int
    title: str
    type: str
    url: str
    description: Optional[str]
    created_at: str
    topic_name: str  # Added to match DocumentResponse

class TopicModel(BaseModel):
    topic: str
    competencies: List[CompetencyModel]
    documents: List[DocumentModel] = []  # Changed from files to documents

class DepartmentModel(BaseModel):
    department: str
    topics: List[TopicModel]

def get_db_connection():
    conn = sqlite3.connect('medical_assessment.db')
    conn.row_factory = sqlite3.Row
    return conn

@router.get("/", response_model=DepartmentModel)
async def get_curriculum():
    """
    Get the complete medical curriculum structure including departments, topics, and competencies.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get department
        cursor.execute('SELECT * FROM departments LIMIT 1')
        department = cursor.fetchone()
        
        if not department:
            raise HTTPException(status_code=404, detail="No curriculum data found")

        # Get all topics for the department
        cursor.execute('''
            SELECT t.id, t.name 
            FROM topics t
            WHERE t.department_id = ?
            ORDER BY t.id
        ''', (department['id'],))
        
        topics = cursor.fetchall()
        
        # Format the response
        curriculum_data = {
            "department": department['name'],
            "topics": []
        }

        for topic in topics:
            # Get competencies for each topic
            cursor.execute('''
                SELECT 
                    c.competency_code,
                    c.description as competency,
                    GROUP_CONCAT(DISTINCT tm.name) as teaching_methods,
                    GROUP_CONCAT(DISTINCT am.name) as assessment_methods
                FROM competencies c
                LEFT JOIN competency_teaching_methods ctm ON c.id = ctm.competency_id
                LEFT JOIN teaching_methods tm ON ctm.teaching_method_id = tm.id
                LEFT JOIN competency_assessment_methods cam ON c.id = cam.competency_id
                LEFT JOIN assessment_methods am ON cam.assessment_method_id = am.id
                WHERE c.topic_id = ?
                GROUP BY c.id
                ORDER BY c.competency_code
            ''', (topic['id'],))
            
            competencies = cursor.fetchall()
            
            # Get documents for this topic
            cursor.execute('''
                SELECT d.id, d.title, d.type, d.url, d.description, d.created_at
                FROM documents d
                JOIN topic_documents td ON d.id = td.document_id
                WHERE td.topic_id = ?
                ORDER BY d.created_at DESC
            ''', (topic['id'],))
            
            documents = cursor.fetchall()
            
            topic_data = {
                "topic": topic['name'],
                "competencies": [{
                    "competency_code": comp['competency_code'],
                    "competency": comp['competency'],
                    "teaching_methods": comp['teaching_methods'].split(',') if comp['teaching_methods'] else [],
                    "assessment_methods": comp['assessment_methods'].split(',') if comp['assessment_methods'] else []
                } for comp in competencies],
                "documents": [{
                    "id": doc['id'],
                    "title": doc['title'],
                    "type": doc['type'],
                    "url": doc['url'],
                    "description": doc['description'],
                    "created_at": doc['created_at'],
                    "topic_name": topic['name']  # Add topic_name to response
                } for doc in documents]
            }
            curriculum_data["topics"].append(topic_data)

        conn.close()
        return curriculum_data

    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.get("/topics", response_model=List[str])
async def get_topics():
    """
    Get a list of all topics in the curriculum.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT name FROM topics ORDER BY id')
        topics = cursor.fetchall()
        
        conn.close()
        return [topic['name'] for topic in topics]

    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/topics/{topic_name}/competencies", response_model=List[CompetencyModel])
async def get_topic_competencies(topic_name: str):
    """
    Get all competencies for a specific topic.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                c.competency_code,
                c.description as competency,
                GROUP_CONCAT(DISTINCT tm.name) as teaching_methods,
                GROUP_CONCAT(DISTINCT am.name) as assessment_methods
            FROM topics t
            JOIN competencies c ON t.id = c.topic_id
            LEFT JOIN competency_teaching_methods ctm ON c.id = ctm.competency_id
            LEFT JOIN teaching_methods tm ON ctm.teaching_method_id = tm.id
            LEFT JOIN competency_assessment_methods cam ON c.id = cam.competency_id
            LEFT JOIN assessment_methods am ON cam.assessment_method_id = am.id
            WHERE t.name = ?
            GROUP BY c.id
            ORDER BY c.competency_code
        ''', (topic_name,))
        
        competencies = cursor.fetchall()
        
        if not competencies:
            raise HTTPException(status_code=404, detail=f"Topic '{topic_name}' not found")
        
        conn.close()
        
        return [{
            "competency_code": comp['competency_code'],
            "competency": comp['competency'],
            "teaching_methods": comp['teaching_methods'].split(',') if comp['teaching_methods'] else [],
            "assessment_methods": comp['assessment_methods'].split(',') if comp['assessment_methods'] else []
        } for comp in competencies]

    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.get("/topics/{topic_name}/documents", response_model=List[DocumentModel])
async def get_topic_documents(topic_name: str):
    """
    Get all documents associated with a specific topic.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT d.id, d.title, d.type, d.url, d.description, d.created_at
            FROM documents d
            JOIN topic_documents td ON d.id = td.document_id
            JOIN topics t ON td.topic_id = t.id
            WHERE t.name = ?
            ORDER BY d.created_at DESC
        ''', (topic_name,))
        
        documents = cursor.fetchall()
        
        if not documents:
            return []
        
        conn.close()
        
        return [{
            "id": doc['id'],
            "title": doc['title'],
            "type": doc['type'],
            "url": doc['url'],
            "description": doc['description'],
            "created_at": doc['created_at'],
            "topic_name": topic_name  # Add topic_name to response
        } for doc in documents]

    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.get("/{department_name}", response_model=DepartmentModel)
async def get_department_curriculum(department_name: str):
    """
    Get the curriculum structure for a specific department.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get department
        cursor.execute('SELECT * FROM departments WHERE name LIKE ?', (f"%{department_name}%",))
        department = cursor.fetchone()
        
        if not department:
            raise HTTPException(status_code=404, detail=f"Department '{department_name}' not found")

        # Get all topics for the department
        cursor.execute('''
            SELECT t.id, t.name 
            FROM topics t
            WHERE t.department_id = ?
            ORDER BY t.id
        ''', (department['id'],))
        
        topics = cursor.fetchall()
        
        curriculum_data = {
            "department": department['name'],
            "topics": []
        }

        for topic in topics:
            # Get competencies with teaching methods and assessment methods
            cursor.execute('''
                SELECT 
                    c.id as competency_id,
                    c.competency_code,
                    c.description as competency,
                    GROUP_CONCAT(DISTINCT tm.name) as teaching_methods,
                    GROUP_CONCAT(DISTINCT am.name) as assessment_methods
                FROM competencies c
                LEFT JOIN competency_teaching_methods ctm ON c.id = ctm.competency_id
                LEFT JOIN teaching_methods tm ON ctm.teaching_method_id = tm.id
                LEFT JOIN competency_assessment_methods cam ON c.id = cam.competency_id
                LEFT JOIN assessment_methods am ON cam.assessment_method_id = am.id
                WHERE c.topic_id = ?
                GROUP BY c.id
                ORDER BY c.competency_code
            ''', (topic['id'],))
            
            competencies = cursor.fetchall()
            
            # Get documents for this topic
            cursor.execute('''
                SELECT d.id, d.title, d.type, d.url, d.description, d.created_at
                FROM documents d
                JOIN topic_documents td ON d.id = td.document_id
                WHERE td.topic_id = ?
                ORDER BY d.created_at DESC
            ''', (topic['id'],))
            
            documents = cursor.fetchall()
            
            topic_data = {
                "topic": topic['name'],
                "competencies": [],
                "documents": [{
                    "id": doc['id'],
                    "title": doc['title'],
                    "type": doc['type'],
                    "url": doc['url'],
                    "description": doc['description'],
                    "created_at": doc['created_at'],
                    "topic_name": topic['name']  # Add topic_name to response
                } for doc in documents]
            }

            for comp in competencies:
                # Get assessments for this competency
                cursor.execute('''
                    SELECT id, title
                    FROM assessments
                    WHERE competency_id = ?
                    ORDER BY created_at
                ''', (comp['competency_id'],))
                
                assessments = cursor.fetchall()

                competency_data = {
                    "competency_code": comp['competency_code'],
                    "competency": comp['competency'],
                    "teaching_methods": comp['teaching_methods'].split(',') if comp['teaching_methods'] else [],
                    "assessments": [{
                        "id": assessment['id'],
                        "title": assessment['title']
                    } for assessment in assessments] if assessments else [],
                    "assessment_methods": comp['assessment_methods'].split(',') if comp['assessment_methods'] else []
                }
                topic_data["competencies"].append(competency_data)

            curriculum_data["topics"].append(topic_data)

        conn.close()
        return curriculum_data

    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")