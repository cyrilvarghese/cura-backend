from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, validator

class ConceptModal(BaseModel):
    specific: str
    general: str
    lateral: str

class Options(BaseModel):
    A: str | None = None
    B: str | None = None
    C: str | None = None
    D: str | None = None

class BaseQuestion(BaseModel):
    station_title: str
    addressed_gap: str
    prompt: str
    explanation: str
    concept_modal: ConceptModal

class MCQQuestion(BaseQuestion):
    question_format: Literal["MCQ"]
    options: Options
    mcq_correct_answer_key: str
    expected_answer: None = None

class WrittenQuestion(BaseQuestion):
    question_format: Literal["written"]
    options: None = None
    mcq_correct_answer_key: None = None
    expected_answer: str

class BaseStudentResponse(BaseModel):
    pass

class MCQStudentResponse(BaseStudentResponse):
    student_mcq_choice_key: str
    student_written_answer: None = None

class WrittenStudentResponse(BaseStudentResponse):
    student_mcq_choice_key: None = None
    student_written_answer: str

class MCQBody(BaseModel):
    question: MCQQuestion
    student_response: MCQStudentResponse

class WrittenBody(BaseModel):
    question: WrittenQuestion
    student_response: WrittenStudentResponse

class OSCEFeedbackRequest(BaseModel):
    case_id: str
    body: Body

    @validator('body')
    def validate_body_type(cls, v):
        question_format = v.question.question_format
        if question_format == "MCQ":
            if not isinstance(v, MCQBody):
                raise ValueError("MCQ questions must use MCQBody format")
        elif question_format == "written":
            if not isinstance(v, WrittenBody):
                raise ValueError("Written questions must use WrittenBody format")
        return v

    class Config:
        json_schema_extra = {
            "examples": {
                "mcq": {
                    "case_id": "1",
                    "body": {
                        "question": {
                            "station_title": "Differentiating Based on Lesion Duration",
                            "question_format": "MCQ",
                            "addressed_gap": "Gap: Failure to use lesion duration as a key differentiator between urticarial vasculitis and chronic spontaneous urticaria.",
                            "prompt": "A patient presents with itchy, red welts...",
                            "options": {
                                "A": "Urticarial vasculitis",
                                "B": "Chronic spontaneous urticaria",
                                "C": "Erythema multiforme",
                                "D": "Fixed drug eruption"
                            },
                            "mcq_correct_answer_key": "B",
                            "expected_answer": None,
                            "explanation": "Lesions lasting <24 hours without residual changes...",
                            "concept_modal": {
                                "specific": "Lesion duration is a critical differentiating feature...",
                                "general": "Careful history taking regarding...",
                                "lateral": "Temporal patterns are key in differentiating..."
                            }
                        },
                        "student_response": {
                            "student_mcq_choice_key": "B",
                            "student_written_answer": None
                        }
                    }
                },
                "written": {
                    "case_id": "1",
                    "body": {
                        "question": {
                            "station_title": "Impact of Normal Complements",
                            "question_format": "written",
                            "addressed_gap": "Gap: Difficulty interpreting normal complement levels in a patient otherwise resembling urticarial vasculitis.",
                            "prompt": "Consider a patient with persistent (>48h) urticarial lesions leaving bruising, arthralgias, and a positive ANA (1:160). However, their C3 and C4 levels are normal. What does this finding suggest about the diagnosis?",
                            "options": None,
                            "mcq_correct_answer_key": None,
                            "expected_answer": "Normal complement levels make Hypocomplementemic Urticarial Vasculitis Syndrome (HUVS) unlikely. The diagnosis could still be normocomplementemic UV.",
                            "explanation": "While low complements are classic for HUVS, UV can occur with normal levels (normocomplementemic UV). This finding helps in subtyping UV.",
                            "concept_modal": {
                                "specific": "Normocomplementemic UV exists and must be considered, impacting the extent of systemic workup.",
                                "general": "Absence of a 'classic' lab finding doesn't always exclude a diagnosis; consider atypical presentations and subtypes.",
                                "lateral": "Seronegative rheumatoid arthritis, atypical presentations of infections."
                            }
                        },
                        "student_response": {
                            "student_mcq_choice_key": None,
                            "student_written_answer": "I dont know"
                        }
                    }
                }
            }
        }

# Type discriminator for Body
Body = MCQBody | WrittenBody 