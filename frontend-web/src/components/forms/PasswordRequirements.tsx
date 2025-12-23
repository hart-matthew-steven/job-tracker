import { describeViolation, PASSWORD_MIN_LENGTH, type PasswordViolation } from "../../lib/passwordPolicy";

const ORDER: PasswordViolation[] = [
  "min_length",
  "uppercase",
  "lowercase",
  "number",
  "special_char",
  "contains_email",
  "contains_name",
  "denylist_common",
];

type Props = {
  violations: Set<PasswordViolation>;
  minLength?: number;
};

export default function PasswordRequirements({ violations, minLength = PASSWORD_MIN_LENGTH }: Props) {
  return (
    <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-950/30 dark:text-slate-300">
      <div className="font-semibold text-slate-700 dark:text-slate-200">Password requirements</div>
      <ul className="mt-2 space-y-1">
        {ORDER.map((code) => {
          const met = !violations.has(code);
          return (
            <li key={code} className={met ? "text-emerald-600 dark:text-emerald-400" : ""}>
              <span className="mr-1 font-semibold">{met ? "✓" : "•"}</span>
              {describeViolation(code, { minLength })}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

