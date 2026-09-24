# Use Case: Autenticarse

## Overview

**Use Case ID:** UC-001  
**Use Case Name:** Autenticarse  
**Primary Actor:** Participante  
**Goal:** Sign in with a personal account so that the agent knows who is asking and what the person may do  
**Status:** Draft

**Traces to:** FR-013, FR-021 · NFR-006, NFR-009, NFR-013

## Preconditions

- The chat page is available
- New participants know the event code shared during the talk
- Registration is open when a new account is needed

## Main Success Scenario

1. Participant opens the chat page.
2. System asks the participant to sign in or to create an account.
3. Participant chooses to create an account and enters an email address, a password and the event code.
4. System validates the email address, the password and the event code.
5. System creates the account with the Participante role and confirms it without further steps.
6. System signs the participant in.
7. System shows the chat and asks the participant to choose an answer profile (see UC-002).

## Alternative Flows

### A1: Returning Participant

**Trigger:** Participant already has an account and chooses to sign in (step 3)  
**Flow:**

1. Participant enters the email address and the password.
2. System verifies the credentials.
3. Use case continues at step 6.

### A2: Wrong Credentials

**Trigger:** Email address and password do not match an account (step 6)  
**Flow:**

1. System tells the participant that the credentials are not correct, without saying which one failed.
2. Use case continues at step 3.

### A3: Too Many Failed Attempts

**Trigger:** Participant fails to sign in five times in a row (step 6)  
**Flow:**

1. System blocks sign-in for that account for 15 minutes and tells the participant when to try again.
2. Use case ends.

### A4: Invalid Event Code

**Trigger:** The event code is wrong (step 4)  
**Flow:**

1. System tells the participant that the code is not valid and asks to check it with the speaker.
2. Use case continues at step 3.

### A5: Registration Closed

**Trigger:** The speaker has closed registration or the account limit has been reached (step 4)  
**Flow:**

1. System tells the participant that new accounts are not available right now.
2. Use case ends.

### A6: Email Already Registered

**Trigger:** An account with that email address already exists (step 4)  
**Flow:**

1. System tells the participant that the email address already has an account and offers to sign in.
2. Use case continues at step 3.

### A7: Password Not Acceptable

**Trigger:** The password does not meet the password rules (step 4)  
**Flow:**

1. System explains the rules the password must meet.
2. Use case continues at step 3.

### A8: Signing In as Ponente

**Trigger:** The account belongs to the speaker (step 6)  
**Flow:**

1. System signs the speaker in with the Ponente role.
2. System shows the chat with the same functions as a participant plus the speaker analysis.
3. Use case continues at step 7.

## Postconditions

### Success Postconditions

- The person is signed in with their role (Participante or Ponente).
- A new account, if created, exists and is ready to use without email confirmation.
- The person can use the chat until the session ends.

### Failure Postconditions

- The person is not signed in and no account is created.
- No information about existing accounts has been revealed.

## Business Rules

### BR-001: Event Code

A new account can only be created with the event code shared during the talk. The event code replaces email confirmation.

### BR-002: Registration Window

The speaker decides when registration is open and can close it at any time. Closing registration does not affect people who already have an account.

### BR-003: Ponente Accounts

Ponente accounts are created only by the organizer. Nobody can obtain the Ponente role by creating an account or by editing their own data.

### BR-004: Password Rules

A password has at least 8 characters and contains letters and numbers.

### BR-005: Failed Attempts

After five failed sign-in attempts in a row the account is blocked for 15 minutes.

### BR-006: No Password Recovery

The demo does not offer password recovery. A participant who forgets the password creates a new account with another email address.

### BR-007: Account Limit

At most 100 accounts exist for the event. The limit protects the project budget.

### BR-008: Session Duration

A person stays signed in for up to 12 hours, enough for the whole event.

### BR-009: Email Privacy

The email address only identifies the account. It is never shown to other participants or in the speaker analysis.
