# LangChain Diagnosis Feedback API

This module provides a LangChain-based implementation of the diagnosis feedback API using OpenAI models instead of the Gemini API.

## Overview

The `diagnosis_feedback_langchain.py` file implements an endpoint for generating detailed feedback on a student's diagnostic process:

- `/feedback/diagnosis/feedback-langchain` - Generates comprehensive analysis of a student's diagnostic approach, reasoning, and accuracy

## Features

- Uses LangChain with OpenAI's models (defaults to gpt-4o)
- Structured output parsing for consistent feedback format
- Comprehensive error handling and detailed logging
- Session management integration for storing feedback

## Usage

Call the diagnosis feedback endpoint to generate detailed feedback on the diagnostic process:

```http
GET /feedback/diagnosis/feedback-langchain
```

This will:
- Retrieve student data from the active session, including:
  - Clinical findings recorded
  - Physical examinations performed
  - Tests ordered
  - Diagnosis submissions
  - Final diagnosis
- Load the case context and expected diagnoses
- Process the data using LangChain
- Store the results in the session
- Return detailed feedback on the diagnostic process

## Response Format

The endpoint returns a JSON response with the following structure:

```json
{
  "case_id": "123",
  "student_id": "456",
  "timestamp": "2023-07-01T12:34:56.789Z",
  "feedback_result": {
    "diagnostic_accuracy": "Detailed assessment of accuracy",
    "data_interpretation": "Assessment of interpretation skills",
    "differential_diagnosis": "Evaluation of differential diagnosis",
    "clinical_reasoning": "Analysis of reasoning process",
    "overall_feedback": "Comprehensive feedback",
    "improvement_suggestions": "Areas for improvement"
  },
  "metadata": {
    "processing_time_seconds": 3.2,
    "model_version": "gpt-4o",
    "source": "langchain"
  }
}
```

## Configuration

The implementation uses the following environment variables:

- `OPENAI_API_KEY` - Your OpenAI API key for authentication

## Dependencies

- LangChain
- OpenAI API
- FastAPI

## Comparison with Gemini Implementation

The LangChain implementation provides a more modular approach compared to the direct Gemini implementation:

1. **Flexibility**: Can easily swap out OpenAI models with other LLM providers
2. **Structure**: Uses LangChain's structured components for better organization
3. **Consistency**: Similar interface to other LangChain-based feedback modules
4. **Performance**: May have different performance characteristics based on the chosen model

Both implementations provide the same core functionality and can be used interchangeably. 