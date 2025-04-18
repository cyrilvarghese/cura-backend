from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
import sqlite3
from pydantic import BaseModel
from enum import Enum
from utils.supabase_document_ops import SupabaseDocumentOps

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

class DocumentStatus(str, Enum):
    CASE_REVIEW_PENDING = "CASE_REVIEW_PENDING"
    CASE_REVIEW_IN_PROGRESS = "CASE_REVIEW_IN_PROGRESS"
    CASE_REVIEW_COMPLETE = "CASE_REVIEW_COMPLETE"
    DATA_REVIEW_IN_PROGRESS = "DATA_REVIEW_IN_PROGRESS"
    PUBLISHED = "PUBLISHED"

class DocumentModel(BaseModel):
    id: int
    title: str
    type: str
    url: str
    description: Optional[str]
    created_at: str
    topic_name: Optional[str] = None  # Made optional
    department_name: Optional[str] = None  # Added field
    google_doc_id: Optional[str] = None
    google_doc_link: Optional[str] = None
    status: DocumentStatus = DocumentStatus.CASE_REVIEW_PENDING

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

@router.get("", response_model=DepartmentModel)
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
                SELECT 
                    d.id, 
                    d.title, 
                    d.type, 
                    d.url, 
                    d.description, 
                    d.created_at,
                    d.google_doc_id,  -- Added field
                    d.google_doc_link  -- Added field
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
                    "topic_name": topic['name'],
                    "google_doc_id": doc['google_doc_id'],  # Added field
                    "google_doc_link": doc['google_doc_link']  # Added field
                } for doc in documents]
            }
            curriculum_data["topics"].append(topic_data)

        conn.close()
        return curriculum_data

    except sqlite3.Error as e:
        import traceback
        print(f"Exception in get_curriculum:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        import traceback
        print(f"Exception in get_curriculum:\n{traceback.format_exc()}")
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
        import traceback
        print(f"Exception in get_topic_competencies:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        import traceback
        print(f"Exception in get_topic_competencies:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.get("/topics/{topic_name}/documents", response_model=List[DocumentModel])
async def get_topic_documents(topic_name: str):
    """
    Get all documents associated with a specific topic.
    Case insensitive topic name matching.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                d.id, 
                d.title, 
                d.type, 
                d.url, 
                d.description, 
                d.created_at,
                d.google_doc_id,  -- Added field
                d.google_doc_link  -- Added field
            FROM documents d
            JOIN topic_documents td ON d.id = td.document_id
            JOIN topics t ON td.topic_id = t.id
            WHERE LOWER(t.name) = LOWER(?)
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
            "topic_name": topic_name,
            "google_doc_id": doc['google_doc_id'],  # Added field
            "google_doc_link": doc['google_doc_link']  # Added field
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
                SELECT d.id, d.title, d.type, d.url, d.description, d.created_at, d.google_doc_id, d.google_doc_link
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
                    "topic_name": topic['name'],
                    "google_doc_id": doc['google_doc_id'],
                    "google_doc_link": doc['google_doc_link']
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
        import traceback
        print(f"Exception in get_department_curriculum:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        import traceback
        print(f"Exception in get_department_curriculum:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.get("/{department_name}/documents", response_model=List[DocumentModel])
async def get_department_documents(department_name: str):
    """
    Get all documents associated with a specific department.
    Case insensitive department name matching.
    """
    try:
        # First get the department ID
        department_id = await SupabaseDocumentOps.get_department_id(department_name)
        
        # Then get all documents for that department
        documents = await SupabaseDocumentOps.get_department_documents(department_id)
        
        if not documents:
            return []
            
        # Format the response to match the expected structure
        return [{
            "id": doc.get('id'),
            "title": doc.get('title'),
            "type": doc.get('type'),
            "url": doc.get('url'),
            "description": doc.get('description'),
            "created_at": doc.get('created_at'),
            "google_doc_id": doc.get('google_doc_id'),
            "google_doc_link": doc.get('google_doc_link'),
            "status": doc.get('status'),
            "department_name": department_name
        } for doc in documents]

    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error fetching department documents: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to fetch department documents: {str(e)}"
        )