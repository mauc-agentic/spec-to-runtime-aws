# Test Case: Conversación del participante y análisis del Ponente

## Overview

**ID:** TC-001  
**Goal:** A new participant creates an account, asks the agent a question about the repository and a follow-up, finds both in their history, and the Ponente then sees those two questions reflected in the top 10 without any participant being identified.  
**Priority:** Critical  
**Status:** Draft

## Roles

- Participante (creates an account, asks a question and a follow-up, reviews the history)
- Ponente (signs in with the speaker account and asks for the most frequent questions)

## Preconditions

- The repository documents are synchronized at least once (see [UC-003](../use_cases/UC-003-sincronizar-documentos-del-repositorio.md)); the Knowledge Base is seeded by the synchronization function `spec-to-runtime-sync`.
- Event data is empty: no questions, usage counters or conversation memory exist. It is emptied with `scripts/reset_event_data.py --yes` (without `--users`).
- Registration is open and the account limit has not been reached. The event code is the one stored in the event secret (`event_secret_arn` output of the infrastructure); it is read from there and never written in this document.
- A Ponente account `tc001-ponente@example.com` exists in the Ponente group. The organizer creates it by hand with the Cognito CLI (see `docs/charla/infraestructura-base.md`); its password is held by the organizer.
- No account `tc001-participante@example.com` exists.
- The daily usage limits of both roles and the project-wide limit have not been reached.

## Flow

| Step | Name | Description | Test Data | Use Case |
|------|------|-------------|-----------|----------|
| 1 | Create participant account | Participant opens the chat page, chooses to create an account and enters the email address, the password and the event code. System confirms the account, signs the participant in and shows the chat. | Email: `tc001-participante@example.com`, Password: `Prueba2026`, Event code: current event code | [UC-001](../use_cases/UC-001-autenticarse.md) |
| 2 | Verify participant signed in | The chat is shown with the Participante role and no speaker analysis is offered. The answer profile of the conversation is General. | Profile: General | - |
| 3 | Ask first question | Participant writes the question and submits it. The status appears within 2 seconds and moves through "Queued", "Searching" and "Writing" while the answer text grows. | Question: `¿Qué es AIUP?` | [UC-004](../use_cases/UC-004-consultar-al-agente-sobre-el-repositorio.md) |
| 4 | Verify cited answer | The complete answer is formatted in short sections and includes at least one link to a document of the repository. | - | - |
| 5 | Ask follow-up | In the same conversation, without repeating the context, the participant writes a question that refers to the previous answer. | Question: `¿y cómo se aplica en este repo?` | [UC-005](../use_cases/UC-005-continuar-una-conversación.md) |
| 6 | Verify follow-up in context | The answer is about how AIUP is applied in this repository, so the agent understood what "se aplica" refers to, and it appears below the first answer in the same conversation. | - | - |
| 7 | Open history | Participant opens the conversation history. Exactly one conversation is listed, with `¿Qué es AIUP?` as its first question and two questions in total. | - | [UC-006](../use_cases/UC-006-consultar-historial-de-conversaciones.md) |
| 8 | Verify conversation detail | Participant selects the conversation. Both questions are shown with their answers, the cited documents with links, the profile General and the date. | Profile: General | - |
| 9 | Sign out and sign in as Ponente | Participant signs out. The speaker signs in with the Ponente account and the chat shows the speaker analysis in addition to the regular functions. | Email: `tc001-ponente@example.com`, Password: Ponente password held by the organizer | [UC-001](../use_cases/UC-001-autenticarse.md) |
| 10 | Ask for most frequent questions | Ponente writes the request without naming a period and submits it. The status appears within 2 seconds and the report is written. | Request: `¿Cuáles fueron las preguntas más frecuentes?` | [UC-007](../use_cases/UC-007-consultar-top-10-de-preguntas.md) |
| 11 | Verify top 10 report | The report states that the whole event was analyzed and that 2 questions were analyzed. It lists topics with position, name, number of questions, share and one example, and the counts of all topics add up to 2. The example questions come from steps 3 and 5. | Total analyzed: 2 | - |
| 12 | Verify Ponente history is private | Ponente opens the conversation history. Only the conversation with the request of step 10 is listed; the participant's conversation is not. | - | [UC-006](../use_cases/UC-006-consultar-historial-de-conversaciones.md) |

## Validation

1. **Answers come from the repository**: Both answers of the participant include links to repository documents, and neither contains content the repository does not support.
2. **Context is kept inside one conversation**: The history shows the two questions of the participant as one conversation, not two, and the follow-up answer refers to AIUP without the participant repeating it.
3. **Report reflects only participant questions**: The top 10 counts the 2 questions of the participant and does not count the request of the Ponente itself.
4. **Anonymity**: Neither the report nor any example shows the email address `tc001-participante@example.com`, a name or an identifier of the participant.
5. **Privacy between roles**: The Ponente history shows only the Ponente's own request and report; the participant's history shows only the participant's own two questions.
6. **Daily usage**: The participant used 2 questions of the daily allowance and the Ponente used 1 of theirs; consulting the history did not count in either.
7. **Speed**: In steps 3, 5 and 10 the status was visible within 2 seconds of submitting; the participant's answers were complete within 10 seconds and the report within 20 seconds, allowing a longer first request after a deployment while the agent starts.

## Postconditions

- Account `tc001-participante@example.com` in the Participante role.
- One conversation of that participant with two completed questions (`¿Qué es AIUP?` and `¿y cómo se aplica en este repo?`), their answers, cited documents and conversation memory.
- One conversation of the Ponente with the request `¿Cuáles fueron las preguntas más frecuentes?` and its report.
- Daily usage of 2 for the participant and 1 for the Ponente, and 3 in the project total.
- Cleanup: run `scripts/reset_event_data.py --yes --users`. It removes the questions, usage counters and conversation memory together with the participant account. The Ponente account, the Knowledge Base and the documents stay untouched (they are seeded, not created by the journey).
