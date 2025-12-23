export const PASSWORD_MIN_LENGTH = 14;

export type PasswordViolation =
  | "min_length"
  | "uppercase"
  | "lowercase"
  | "number"
  | "special_char"
  | "contains_email"
  | "contains_name"
  | "denylist_common";

const COMMON_WEAK_PASSWORDS = new Set([
  "password",
  "password123",
  "123456",
  "123456789",
  "12345678",
  "qwerty",
  "abc123",
  "letmein",
  "111111",
  "iloveyou",
  "admin",
  "welcome",
  "monkey",
  "dragon",
  "football",
  "baseball",
  "123123",
  "qwerty123",
  "zaq12wsx",
  "trustno1",
  "passw0rd",
  "sunshine",
  "princess",
  "login",
  "whatever",
]);

function normalize(value?: string | null) {
  return (value ?? "").trim().toLowerCase();
}

function hasUppercase(value: string) {
  return /[A-Z]/.test(value);
}

function hasLowercase(value: string) {
  return /[a-z]/.test(value);
}

function hasNumber(value: string) {
  return /[0-9]/.test(value);
}

function hasSpecial(value: string) {
  return /[^A-Za-z0-9]/.test(value);
}

export function evaluatePassword(
  password: string,
  {
    email,
    name,
    minLength = PASSWORD_MIN_LENGTH,
  }: { email?: string | null; name?: string | null; minLength?: number } = {}
): PasswordViolation[] {
  const pw = password ?? "";
  const violations: PasswordViolation[] = [];
  const normalizedPassword = pw.toLowerCase();

  if ((pw ?? "").length < Math.max(minLength, 1)) violations.push("min_length");
  if (!hasUppercase(pw)) violations.push("uppercase");
  if (!hasLowercase(pw)) violations.push("lowercase");
  if (!hasNumber(pw)) violations.push("number");
  if (!hasSpecial(pw)) violations.push("special_char");

  const normalizedEmail = normalize(email);
  if (normalizedEmail) {
    if (normalizedPassword.includes(normalizedEmail)) {
      violations.push("contains_email");
    } else {
      const local = normalizedEmail.split("@")[0];
      if (local && normalizedPassword.includes(local)) violations.push("contains_email");
    }
  }

  const normalizedName = normalize(name);
  if (normalizedName && normalizedPassword.includes(normalizedName)) {
    violations.push("contains_name");
  }

  if (COMMON_WEAK_PASSWORDS.has(normalizedPassword)) {
    violations.push("denylist_common");
  }

  const unique: PasswordViolation[] = [];
  const seen = new Set<string>();
  for (const v of violations) {
    if (seen.has(v)) continue;
    seen.add(v);
    unique.push(v);
  }
  return unique;
}

export function describeViolation(code: PasswordViolation, { minLength = PASSWORD_MIN_LENGTH }: { minLength?: number } = {}): string {
  switch (code) {
    case "min_length":
      return `At least ${minLength} characters`;
    case "uppercase":
      return "At least one uppercase letter (A-Z)";
    case "lowercase":
      return "At least one lowercase letter (a-z)";
    case "number":
      return "At least one number (0-9)";
    case "special_char":
      return "At least one special character (!@#$, etc.)";
    case "contains_email":
      return "Cannot contain your email address";
    case "contains_name":
      return "Cannot contain your name";
    case "denylist_common":
      return "Cannot be a common password";
    default:
      return "Password requirement not met";
  }
}

