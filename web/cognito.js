// Acceso con Cognito llamando directamente a su API pública (sin SDK): el cliente no tiene secreto.
const { region, clientId } = window.APP_CONFIG;
const ENDPOINT = `https://cognito-idp.${region}.amazonaws.com/`;

export class AuthError extends Error {}

// Mensajes en el tono de UC-001: dicen qué pasó y cómo seguir; nunca revelan si un correo existe.
const MESSAGES = {
  REGISTRATION_CLOSED: "El registro está cerrado por ahora. Pregunta al ponente.",
  INVALID_EVENT_CODE: "El código del evento no es válido. Revísalo con el ponente.",
  ACCOUNT_LIMIT_REACHED: "Ya no hay cupos para crear cuentas nuevas.",
  UsernameExistsException: "Ese correo ya tiene cuenta. Usa Entrar.",
  InvalidPasswordException: "La contraseña necesita al menos 8 caracteres, con letras y números.",
  NotAuthorizedException: "El correo o la contraseña no son correctos.",
  UserNotFoundException: "El correo o la contraseña no son correctos.",
  PasswordResetRequiredException: "El correo o la contraseña no son correctos.",
  TooManyRequestsException: "Demasiados intentos. Espera unos minutos e inténtalo de nuevo.",
  LimitExceededException: "Demasiados intentos. Espera unos minutos e inténtalo de nuevo.",
  InvalidParameterException: "Revisa el correo y la contraseña.",
};

function explain(type, message) {
  const code = /PreSignUp failed with error (\w+)/.exec(message || "")?.[1];
  return MESSAGES[code] || MESSAGES[type] || "No se pudo completar. Inténtalo de nuevo.";
}

async function call(target, body) {
  let response;
  try {
    response = await fetch(ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-amz-json-1.1",
        "X-Amz-Target": `AWSCognitoIdentityProviderService.${target}`,
      },
      body: JSON.stringify(body),
    });
  } catch {
    throw new AuthError("Sin conexión. Revisa tu internet e inténtalo de nuevo.");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new AuthError(explain((data.__type || "").split("#").pop(), data.message));
  return data;
}

export async function signUp(email, password, eventCode) {
  await call("SignUp", {
    ClientId: clientId,
    Username: email,
    Password: password,
    UserAttributes: [{ Name: "email", Value: email }],
    ClientMetadata: { eventCode },
  });
}

export async function signIn(email, password) {
  const data = await call("InitiateAuth", {
    ClientId: clientId,
    AuthFlow: "USER_PASSWORD_AUTH",
    AuthParameters: { USERNAME: email, PASSWORD: password },
  });
  return data.AuthenticationResult.AccessToken;
}

// Solo para decidir qué botones mostrar: la API vuelve a comprobar el rol en cada llamada.
export function groupsOf(token) {
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return payload["cognito:groups"] || [];
  } catch {
    return [];
  }
}

export function isExpired(token) {
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return payload.exp * 1000 < Date.now() + 30000;
  } catch {
    return true;
  }
}
