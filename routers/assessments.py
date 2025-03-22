from fastapi import APIRouter, HTTPException
import sqlite3
from db.connection import get_db_connection

router = APIRouter(
    prefix="/assessments",
    tags=["assessments"],
    responses={404: {"description": "Not found"}}
)

@router.delete("/{assessment_id}")
async def delete_assessment(assessment_id: int):
    """
    Delete an assessment by its ID.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # First check if the assessment exists
        cursor.execute('SELECT id FROM assessments WHERE id = ?', (assessment_id,))
        assessment = cursor.fetchone()

        if not assessment:
            raise HTTPException(status_code=404, detail=f"Assessment with ID {assessment_id} not found")

        # Delete the assessment
        cursor.execute('DELETE FROM assessments WHERE id = ?', (assessment_id,))
        conn.commit()
        conn.close()

        return {"message": f"Assessment {assessment_id} successfully deleted"}

    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}") 