# Use Case: Consultar top 10 de preguntas

## Overview

**Use Case ID:** UC-007  
**Use Case Name:** Consultar top 10 de preguntas  
**Primary Actor:** Ponente  
**Goal:** Learn which topics the audience asked about most, so the speaker can steer the session and close the talk with what interested people the most  
**Status:** Implemented

**Traces to:** FR-012, FR-017, FR-020, FR-022 · NFR-005, NFR-007, NFR-009, NFR-011, NFR-013

## Preconditions

- Ponente has a signed-in account with the Ponente role (see UC-001)
- Participants have asked at least one question stored in the conversation history (see UC-004)
- The daily usage limit of the Ponente and the overall project limit have not been reached

## Main Success Scenario

1. Ponente opens the chat and asks the agent which questions were asked most, optionally naming a period such as "the last hour".
2. Ponente submits the request.
3. System confirms that the person is signed in and has the Ponente role.
4. System accepts the request, counts it in the Ponente's daily usage and shows the status "Queued".
5. System gathers the questions that participants asked in the requested period and shows the status "Analyzing".
6. System groups similar questions into topics and counts the questions of each topic.
7. System ranks the topics by number of questions and keeps the ten with the most questions.
8. System shows the top 10, each topic with its position, name, number of questions, share of the total, one example question and how many of its questions found no source in the repository, together with the period and the total number of questions analyzed.
9. System stores the request and the report in the Ponente's conversation history.

## Alternative Flows

### A1: Person Is Not a Ponente

**Trigger:** Person who submitted the request does not have the Ponente role (step 3)  
**Flow:**

1. System tells the person that this analysis is only available to the Ponente and shows no question or count.
2. System records the request as blocked.
3. Use case ends.

### A2: Session Expired

**Trigger:** Ponente is no longer signed in when the request is submitted (step 3)  
**Flow:**

1. System keeps the written request and asks the Ponente to sign in again.
2. Ponente signs in (see UC-001).
3. Use case continues at step 2.

### A3: Usage Limit Reached

**Trigger:** Ponente has used the daily allowance, or the project-wide limit has been reached (step 3)  
**Flow:**

1. System tells the Ponente which limit was reached and when requests become available again.
2. System records the rejected request without analyzing any question.
3. Use case ends.

### A4: Period Not Clear

**Trigger:** The request does not state a period that the system can understand (step 5)  
**Flow:**

1. System assumes the whole event since the first question and tells the Ponente which period it is using.
2. Use case continues at step 6.

### A5: No Questions in the Period

**Trigger:** Participants asked no questions in the requested period (step 5)  
**Flow:**

1. System tells the Ponente that no questions were found for that period and suggests a wider period.
2. System stores the request and this notice in the Ponente's conversation history.
3. Use case ends.

### A6: Fewer Than Ten Topics

**Trigger:** The questions form fewer than ten topics (step 7)  
**Flow:**

1. System keeps all the topics found.
2. Use case continues at step 8.

### A7: Analysis Takes Too Long or Fails

**Trigger:** The report is not available within the time limit, or the analysis reports an error (step 6)  
**Flow:**

1. System tells the Ponente that the analysis could not be completed and offers to try again.
2. System records the request as failed and does not count it in the daily usage.
3. Use case continues at step 2 if the Ponente retries, or ends.

### A8: Activity Summary Requested

**Trigger:** Ponente asks how much the audience has taken part instead of which topics were asked (step 1)  
**Flow:**

1. System gathers the questions that participants asked in the requested period.
2. System shows the number of questions and participants, the busiest hour, the profiles chosen and the most active participants without saying who they are.
3. Use case ends.

## Postconditions

### Success Postconditions

- The Ponente has seen a report with the ten most asked topics of the period and the total of questions analyzed.
- The request and the report are stored in the Ponente's conversation history.
- The Ponente's daily usage is increased by one.
- The request is recorded as completed and can be traced by its request identifier.
- No participant's name, email or identifier appears in the report.

### Failure Postconditions

- The request is recorded as rejected, blocked or failed, with the reason.
- No question, count or example of any participant has been disclosed.
- Rejected and failed requests are not counted in the daily usage.

## Business Rules

### BR-001: Ponente Only

Only people with the Ponente role can request the top 10. Participants who ask the agent for what others asked receive a refusal and no data.

### BR-002: Period

When the Ponente names no period, the analysis covers the whole event since the first question. The Ponente may narrow it, for example to the last hour or to today. The analysis never covers more than the questions stored for the project.

### BR-003: Grouping

Similar questions are counted together under one topic, and each question belongs to exactly one topic. Topic names are short, at most eight words. The grouping is made when the request is submitted, so two runs on the same data may differ slightly; the counts of all topics always add up to the total analyzed.

### BR-004: Ranking

Topics are ordered by number of questions, from most to fewest. On a tie, the topic with the most recent question comes first. The report shows at most ten topics.

### BR-005: Anonymity

The report never shows who asked. Example questions are shown with personal data masked.

### BR-006: Report Contents

For each topic the report shows position, name, number of questions, share of the total, one example question and the number of its questions that found no source in the repository. It also shows the period and the total number of questions analyzed.

### BR-007: Usage Limits

Each Ponente request counts in the Ponente's daily usage, which allows up to 100 requests per day. The 3000-question limit of the project is shared with the participants. Accepted and blocked requests count; rejected and failed requests do not.

### BR-008: Waiting Time

The Ponente sees the status of the request within 2 seconds. The report should be shown within 20 seconds for most requests; after 90 seconds the request is considered failed.

### BR-009: Content Rules

The report is checked by the same content rules as an answer to a participant, and nothing is shown before it has passed them.

### BR-010: Traceability

Every request receives an identifier that appears in the operation records, so it can be followed from submission to report.

### BR-011: Activity Summary

The activity summary shows the number of questions and participants, the average per participant, the busiest hour in Colombia time, the profiles chosen, how many questions found no source and how many were blocked. The most active participants, up to five, appear as "Participante 1", "Participante 2" and so on by rank. It never shows a name, an email address or an identifier (see BR-005). When the Ponente asks who a participant is, the system explains that the reports do not identify anyone and offers the anonymous summary or the top of questions.
