# Use Case: Continuar una conversación

## Overview

**Use Case ID:** UC-005  
**Use Case Name:** Continuar una conversación  
**Primary Actor:** Participante  
**Goal:** Ask a follow-up question that builds on what was already discussed, without repeating the context  
**Status:** Implemented

**Traces to:** FR-018 · NFR-011, NFR-013

## Preconditions

- Participant is signed in (see UC-001)
- The conversation has at least one answered question (see UC-004)

## Main Success Scenario

1. Participant writes a follow-up question that refers to what was discussed before.
2. Participant submits the question.
3. System recognizes that the question belongs to the open conversation.
4. System recalls the most recent exchanges of the conversation.
5. System processes the question as described in UC-004, understanding what it refers to.
6. System shows the answer and stores it in the same conversation.

## Alternative Flows

### A1: New Conversation

**Trigger:** Participant chooses to start a new conversation (step 1)  
**Flow:**

1. System opens an empty conversation without any previous context.
2. Use case continues at step 2, handled as a first question (see UC-004).

### A2: Context Expired

**Trigger:** The conversation has been idle longer than the time context is kept (step 3)  
**Flow:**

1. System tells the participant that the earlier context is no longer available and that the answer may need more detail in the question.
2. Use case continues at step 5 without the earlier context. The earlier exchanges remain visible in the history.

### A3: Long Conversation

**Trigger:** The conversation has more exchanges than the system remembers (step 4)  
**Flow:**

1. System recalls only the most recent exchanges and leaves out the oldest.
2. Use case continues at step 5.

### A4: Context Not Available

**Trigger:** System cannot recall the earlier exchanges (step 4)  
**Flow:**

1. System tells the participant that it will answer using only the current question.
2. Use case continues at step 5.

## Postconditions

### Success Postconditions

- The follow-up question and its answer belong to the same conversation as the earlier ones.
- The answer takes into account the recent exchanges of the conversation.
- The profile of the conversation is applied, and any usage is counted as in UC-004.

### Failure Postconditions

- The conversation keeps its earlier exchanges unchanged.
- If the follow-up could not be answered, the request is recorded as failed as described in UC-004.

## Business Rules

### BR-001: Context Size

The system remembers the 10 most recent exchanges of a conversation.

### BR-002: Context Duration

Context is kept for 24 hours after the last activity of the conversation. The demo keeps no long-term memory about people.

### BR-003: One Conversation, One Context

The context of a conversation is never mixed with another conversation, and it is never visible to other participants.

### BR-004: Profile Changes

A profile change in the middle of a conversation applies from the next question (see UC-002 BR-003).

### BR-005: Usage

A follow-up question counts in the daily usage like any other question (see UC-004 BR-005 and UC-004 BR-006).
