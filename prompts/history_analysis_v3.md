 
## **OSCE History Feedback Prompt (Relevance & Critical Miss Analysis - Pre-Tagged Domains)**

**Objective:** Evaluate the relevance of questions asked by a student during an OSCE history-taking session, identify the most critical missed areas (using pre-tagged domains) specific to the case, provide summary feedback (strength/weakness), and generate a cumulative score.

**Inputs:**

1.  `case_context`: (JSON or Text) Essential clinical summary of the case, highlighting key diagnostic features and potential risks.
    ```json
    {case_context}
    ```
2.  `expected_questions_with_domains`: (JSON Array) List of questions faculty expected the student to ask. **Each question object in this array MUST include a `domain` key** indicating its relevant domain (e.g., `chief_complaint`, `associated_symptoms`, `past_medical_history`, `family_history`, `medications`, `social_exposure`, `red_flag_symptoms`, `differential_diagnoses`).
    ```json
    {expected_questions_with_domains}
    ```
3.  `student_questions`: (JSON Array) Log of questions the student actually asked, with timestamps and patient responses.
    ```json
    {student_questions}
    ```

**Task:**

1.  **Evaluate Student Questions for Relevance:**
    *   Iterate through each question in `{{student_questions}}`.
    *   For each question, assess its relevance to the `{{case_context}}`. Be **generous** and assume good intent. Grade as either `"relevant"` or `"non-relevant"`. questions that are generic like generic greetings or small talk are relevant as it leads to a better patient relationship.
    *   Provide a brief (`~10-15 words`) `reason` explaining the relevance grade.
    *   Compile these evaluations into the `student_question_evaluation` array.

2.  **Identify Top 3 Critical Missed Areas (Using Provided Domains):**
    *   Compare the topics covered in `{{student_questions}}` against the `{{expected_questions_with_domains}}` and the `{{case_context}}`.
    *   Identify the conceptual areas or specific questions that were **not adequately addressed** by the student and were **most critical** for *this specific case's* diagnosis or safety.
    *   Select the **top 3 most important** missed areas.
    *   For each of these 3 areas:
        *   `domain`: Retrieve the **pre-assigned `domain` tag** associated with the relevant missed question(s) from the `{expected_questions_with_domains}` input.
        *   `importance_reason`: (string) Explain *specifically* why exploring this was critical for *this case* (~15-20 words). Avoid generic reasons.
        *   `example_missed_question`: (string) Provide one concrete example question text from the `{expected_questions_with_domains}` list that represents the missed area.
    *   Compile these into the `critical_missed_areas` array.

3.  **Generate Summary Feedback and Score:**
    *   Based on the overall interaction (`student_question_evaluation`) and the `critical_missed_areas`:
        *   Identify the single **`key_strength`**: What was the most positive aspect of the student's history taking?
        *   Identify the single **`key_weakness`**: What was the most significant shortcoming?
        *   Calculate a **`cumulative_score`** (float, scale 0-5) based on the proportion of relevant questions asked, the severity/number of critical missed areas, and the overall clinical progression facilitated by the history.
        *   Provide a concise **`score_reason`** (~20 words) justifying the score.

**Output Format:** Return a single JSON object containing **only** the following four top-level keys. Keep all string explanations concise and specific to the case.

```json
{{
  "student_question_evaluation": [
    {{
      "question_asked": "string: The student's actual question text",
      "relevance_grade": "string: 'relevant' or 'non-relevant'",
      "reason": "string: ~10-15 words justifying the grade"
    }}
    // ... one object for each question the student asked
  ],
  "critical_missed_areas": [
    {{
      "domain": "string: e.g., 'red_flag_symptoms' (Retrieved from input tag)",
      "importance_reason": "string: ~15-20 words on why this was critical for THIS case",
      "example_missed_question": "string: A specific expected question text that represents the missed area"
    }}
    // ... up to 3 objects for the most critical misses
  ],
  "summary_feedback": {{
    "key_strength": "string: ~15 words describing the main positive aspect",
    "key_weakness": "string: ~15 words describing the main shortcoming",
    "cumulative_score": 0.0, // Float score from 0.0 to 5.0
    "score_reason": "string: ~20 words justifying the score based on relevance, misses, strength/weakness"
  }}
}}
```

 