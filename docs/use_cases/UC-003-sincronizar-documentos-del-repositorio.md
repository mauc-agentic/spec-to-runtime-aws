# Use Case: Sincronizar documentos del repositorio

## Overview

**Use Case ID:** UC-003  
**Use Case Name:** Sincronizar documentos del repositorio  
**Primary Actor:** Ponente  
**Goal:** Bring the agent's knowledge up to date with the current content of the repository  
**Status:** Implemented

**Traces to:** FR-014 · NFR-006, NFR-007, NFR-012

## Preconditions

- Ponente is signed in with the Ponente role (see UC-001)
- The repository on GitHub is reachable

## Main Success Scenario

1. Ponente requests a synchronization of the repository documents.
2. System confirms that the person has the Ponente role.
3. System retrieves the current list of documents from the main branch of the repository.
4. System compares them with the documents already known and identifies the new, changed and removed ones.
5. System loads the new and changed documents and removes the deleted ones.
6. System shows the progress: documents examined, loaded and failed.
7. System shows the final summary and records the synchronization.

## Alternative Flows

### A1: Person Is Not a Ponente

**Trigger:** Person who requested the synchronization does not have the Ponente role (step 2)  
**Flow:**

1. System tells the person that only the Ponente can synchronize documents.
2. Use case ends.

### A2: Synchronization Already Running

**Trigger:** Another synchronization is in progress (step 2)  
**Flow:**

1. System shows the progress of the running synchronization instead of starting a new one.
2. Use case ends.

### A3: Repository Not Reachable

**Trigger:** System cannot reach the repository (step 3)  
**Flow:**

1. System tells the Ponente that the repository could not be read and that the knowledge was not changed.
2. System records the synchronization as failed.
3. Use case ends.

### A4: Nothing Changed

**Trigger:** No document is new, changed or removed (step 4)  
**Flow:**

1. System tells the Ponente that the knowledge is already up to date.
2. System records the synchronization as complete with no changes.
3. Use case ends.

### A5: File Not Supported

**Trigger:** A file has an unsupported type or is too large (step 4)  
**Flow:**

1. System skips the file and lists it as skipped in the summary.
2. Use case continues at step 5.

### A6: Some Documents Fail

**Trigger:** One or more documents cannot be loaded (step 5)  
**Flow:**

1. System keeps loading the remaining documents.
2. System lists the documents that failed in the summary.
3. Use case continues at step 6.

## Postconditions

### Success Postconditions

- Every new or changed document of the repository is available to the agent, and deleted documents are no longer available.
- The synchronization is recorded with the number of documents examined and failed, and its start and end time.
- Citations to the documents lead to the file in the repository.

### Failure Postconditions

- The knowledge keeps the content it had before, except for documents already loaded.
- The synchronization is recorded as failed, with the reason.

## Business Rules

### BR-001: What Is Included

Text files of the repository are included: documents in Markdown, diagrams in PlantUML, infrastructure and application code, and configuration files. Tests and helper scripts (the `tests` and `scripts` folders) are left out: they repeat the vocabulary of the documents and push the reference documents out of the few fragments the agent receives. Binary files, dependency lock files and files over 500 KB are skipped.

### BR-002: Main Branch Only

Only the main branch is synchronized, because it contains the content that has been reviewed and merged.

### BR-003: Sensitive Files

Files that hold secrets, such as environment files, variable files and state files, are never loaded, even if they exist in the repository.

### BR-004: Unchanged Documents

Documents that did not change since the last synchronization are not loaded again.

### BR-005: Removed Documents

A document deleted from the repository is removed from the knowledge.

### BR-006: Everything Is Public

The repository is public, so every synchronized document is available to every user. Documents have no access levels.

### BR-007: One at a Time

Only one synchronization runs at a time.

### BR-008: Record of Each Run

Each synchronization records its outcome, the number of documents examined and failed, and its start and end time.
