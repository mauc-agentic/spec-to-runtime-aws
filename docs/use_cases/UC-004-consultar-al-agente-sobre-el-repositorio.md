# Use Case: Consultar al agente sobre el repositorio

## Overview

**Use Case ID:** UC-004  
**Use Case Name:** Consultar al agente sobre el repositorio  
**Primary Actor:** Participante  
**Goal:** Get a clear answer about the repository, backed by cited documents and written for the participant's chosen profile, without waiting for a blank screen  
**Status:** Implemented

**Traces to:** FR-002, FR-010, FR-011, FR-015, FR-019, FR-021, FR-023 · NFR-005, NFR-007, NFR-010, NFR-011, NFR-013

## Preconditions

- Participant has a signed-in account (see UC-001)
- The current conversation has an answer profile: General unless the participant chose another one (see UC-002)
- The repository documents have been synchronized at least once (see UC-003)
- The daily usage limit of the participant and the overall project limit have not been reached

## Main Success Scenario

1. Participant opens the chat page and writes a question about the repository.
2. Participant submits the question.
3. System confirms that the participant is signed in and still within the usage limits.
4. System checks the question against the content rules.
5. System accepts the question, counts it in the participant's daily usage and shows the status "Queued".
6. System looks up the repository documents related to the question and shows the status "Searching".
7. System starts writing the answer for the participant's profile and shows the status "Writing".
8. System shows the answer text as it is being written, each part only after it has passed the content rules.
9. System completes the answer and shows it formatted in short sections with a link to each cited document in the repository.
10. System stores the question, the answer and its sources in the participant's conversation history.

## Alternative Flows

### A1: Session Expired

**Trigger:** Participant is no longer signed in when the question is submitted (step 3)  
**Flow:**

1. System keeps the written question and asks the participant to sign in again.
2. Participant signs in (see UC-001).
3. Use case continues at step 2.

### A2: Usage Limit Reached

**Trigger:** Participant has used all daily questions, or the project-wide limit has been reached (step 3)  
**Flow:**

1. System tells the participant which limit was reached and when questions become available again.
2. System records the rejected request without consulting the agent.
3. Use case ends.

### A3: Question Not Allowed

**Trigger:** Question is off-topic, tries to manipulate the agent, or is otherwise blocked by the content rules (step 4)  
**Flow:**

1. System tells the participant that this question cannot be answered and suggests asking about the repository or the talk.
2. System records the request as blocked and counts it in the participant's daily usage.
3. Use case ends.

### A4: Question Contains Personal Data

**Trigger:** Question contains personal data such as an email address or a phone number (step 4)  
**Flow:**

1. System masks the personal data in the question and informs the participant.
2. Use case continues at step 5.

### A5: No Related Documents Found

**Trigger:** No repository document is related to the question (step 6)  
**Flow:**

1. System tells the participant that no source was found in the repository and suggests rephrasing the question.
2. System stores the question and this notice in the participant's conversation history.
3. Use case ends.

### A6: Answer Not Allowed

**Trigger:** Part of the answer being written is blocked by the content rules (step 8)  
**Flow:**

1. System stops showing the answer and replaces it with a notice that the answer cannot be shown.
2. System records the request as blocked.
3. Use case ends.

### A7: Answer Takes Too Long or Fails

**Trigger:** The complete answer is not available within the time limit, or the agent reports an error (step 8)  
**Flow:**

1. System tells the participant that the answer could not be completed and offers to try again.
2. System records the request as failed and does not count it in the daily usage.
3. Use case continues at step 2 if the participant retries, or ends.

### A8: Participant Leaves While Waiting

**Trigger:** Participant closes the page or loses the connection (step 8)  
**Flow:**

1. System keeps writing the answer.
2. System stores the question, the answer and its sources in the participant's conversation history.
3. Use case ends. The participant finds the answer in the history (see UC-006).

## Postconditions

### Success Postconditions

- The question, the complete answer and the cited documents are stored in the participant's conversation history.
- The participant's daily usage is increased by one.
- The request is recorded as completed and can be traced by its request identifier.
- The participant has seen the status of the request within 2 seconds of submitting the question.

### Failure Postconditions

- The request is recorded as rejected, blocked or failed, with the reason.
- No answer is stored as if it were valid; only the notice shown to the participant is kept.
- Rejected and failed requests are not counted in the daily usage.
- No question or answer of the participant is visible to other participants.

## Business Rules

### BR-001: Question Length

A question has between 1 and 500 characters.

### BR-002: Answer Profile

The answer is written for the profile chosen in the current conversation at the moment the question is submitted. Basic explains step by step, defines the terms used and ends with a question to check understanding. Technical is detailed, states trade-offs and refers to the decisions recorded in the repository. General is short and avoids jargon.

### BR-003: Answers Come From the Repository

The answer is based only on repository documents. Every statement that relies on a document is accompanied by a link to that file. When no document supports the question, the answer says so and does not invent content.

### BR-004: Content Rules

Both the question and the answer are checked. Off-topic questions, attempts to manipulate the agent and unsafe content are blocked. Personal data is masked. No text is shown to the participant before it has passed these checks.

### BR-005: Usage Limits

Each participant may ask at most 25 questions per day, and the project accepts at most 3000 questions in total. An answer is limited to about 600 words, and the agent may consult at most three sources of information per question.

### BR-006: What Counts as Usage

Accepted and blocked questions count in the daily usage. Rejected and failed requests do not.

### BR-007: Waiting Time

The participant sees the status of the request within 2 seconds and the first part of the answer as soon as it is available. The complete answer should be shown within 10 seconds for most questions; after 60 seconds the request is considered failed.

### BR-008: Privacy

A participant can only see their own questions and answers.

### BR-009: Answer Format

Answers are formatted for a phone screen: short sections, lists where useful, and links to the cited documents.

### BR-010: Traceability

Every request receives an identifier that appears in the operation records, so it can be followed from submission to answer.
