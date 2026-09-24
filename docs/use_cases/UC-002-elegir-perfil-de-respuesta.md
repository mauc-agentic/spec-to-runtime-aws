# Use Case: Elegir perfil de respuesta

## Overview

**Use Case ID:** UC-002  
**Use Case Name:** Elegir perfil de respuesta  
**Primary Actor:** Participante  
**Goal:** Choose how the agent explains things, so that answers match the participant's level of knowledge  
**Status:** Implemented

**Traces to:** FR-016, FR-021

## Preconditions

- Participant is signed in (see UC-001)

## Main Success Scenario

1. Participant opens the profile selector in the chat.
2. System shows the three profiles with a short description of each: Básico, Técnico and General.
3. Participant selects a profile.
4. System applies the profile to the current conversation and confirms the choice.
5. System shows the chat ready for the next question, with the chosen profile visible.

## Alternative Flows

### A1: First Time in the Chat

**Trigger:** Participant has not chosen a profile yet (step 1)  
**Flow:**

1. System asks the participant to choose a profile before the first question.
2. Use case continues at step 2.

### A2: Change During a Conversation

**Trigger:** Participant already has answers in the conversation and selects a different profile (step 3)  
**Flow:**

1. System keeps the answers already given as they are.
2. System tells the participant that the new profile applies from the next question.
3. Use case continues at step 5.

### A3: Answer Being Written

**Trigger:** An answer is still being written when the participant selects a profile (step 3)  
**Flow:**

1. System finishes the current answer with the previous profile.
2. System applies the new profile from the next question.
3. Use case continues at step 5.

### A4: Participant Skips the Choice

**Trigger:** Participant closes the selector without choosing (step 2)  
**Flow:**

1. System uses the General profile and tells the participant that it can be changed at any time.
2. Use case ends.

## Postconditions

### Success Postconditions

- The conversation has the chosen profile.
- The next question of the conversation is answered with that profile.
- New conversations of the participant start with the last chosen profile.

### Failure Postconditions

- The profile of the conversation is unchanged, or General if none had been chosen.

## Business Rules

### BR-001: Available Profiles

There are three profiles. Básico is for students and explains step by step with a glossary. Técnico is for professionals and gives detail, trade-offs and references to recorded decisions. General is for the public and gives short answers without jargon.

### BR-002: Default Profile

When no profile has been chosen, General applies.

### BR-003: Effect of a Change

A profile change applies from the next question and never rewrites answers already given.

### BR-004: Same Profiles for Everyone

The Ponente uses the same three profiles as any participant.

### BR-005: Profile Recorded With Each Request

Every question records the profile that was applied, so the history shows how each answer was written.
