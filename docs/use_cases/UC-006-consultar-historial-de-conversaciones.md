# Use Case: Consultar historial de conversaciones

## Overview

**Use Case ID:** UC-006  
**Use Case Name:** Consultar historial de conversaciones  
**Primary Actor:** Participante  
**Goal:** Review own earlier conversations, with their answers and sources, and pick one up again  
**Status:** Implemented

**Traces to:** FR-021, FR-022 · NFR-009

## Preconditions

- Participant is signed in (see UC-001)

## Main Success Scenario

1. Participant opens the conversation history.
2. System confirms that the participant is signed in.
3. System shows the participant's conversations, most recent first, each with its first question, its date and its number of questions.
4. Participant selects a conversation.
5. System shows every question of the conversation with its answer, the cited documents and the profile that was used.
6. Participant continues the conversation (see UC-005) or goes back to the list.

## Alternative Flows

### A1: Session Expired

**Trigger:** Participant is no longer signed in (step 2)  
**Flow:**

1. System asks the participant to sign in again.
2. Participant signs in (see UC-001).
3. Use case continues at step 3.

### A2: No Conversations Yet

**Trigger:** Participant has no stored conversations (step 3)  
**Flow:**

1. System tells the participant that there are no conversations yet and offers to start one.
2. Use case ends.

### A3: Answer Still Being Written

**Trigger:** The selected conversation has an answer that is still being written (step 5)  
**Flow:**

1. System shows the status of that answer and the text written so far.
2. System keeps updating the text until the answer is complete.
3. Use case continues at step 6.

### A4: Many Conversations

**Trigger:** Participant has more conversations than fit in one list (step 3)  
**Flow:**

1. System shows the 20 most recent conversations and offers to show more.
2. Use case continues at step 4.

## Postconditions

### Success Postconditions

- The participant has seen their own conversations, answers and sources.
- Nothing has been changed.

### Failure Postconditions

- No conversation has been shown.
- No conversation of another person has been disclosed.

## Business Rules

### BR-001: Own Conversations Only

A person sees only their own conversations. This also applies to the Ponente, who sees their own questions and reports but not the participants' conversations.

### BR-002: What Is Shown

For each question the history shows the text, the answer, the cited documents with their links, the profile applied and the date.

### BR-003: Order

Conversations are shown from the most recent to the oldest.

### BR-004: Retention

The history exists while the demo environment exists. When the environment is destroyed at the end of the event, the history is deleted with it.

### BR-005: Read Only

Consulting the history does not change it and does not count in the daily usage.
