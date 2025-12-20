import type { Dispatch, FormEvent, SetStateAction } from "react";

type JobFormState = {
  company_name: string;
  job_title: string;
  location: string;
  job_url: string;
};

type Props = {
  form: JobFormState;
  setForm: Dispatch<SetStateAction<JobFormState>>;
  onCreateJob: (e: FormEvent<HTMLFormElement>) => void | Promise<void>;
  title?: string | null;
  className?: string;
};

export default function JobCard({ form, setForm, onCreateJob, title = "Add Job", className = "" }: Props) {
  return (
    <form
      onSubmit={onCreateJob}
      className={[
        "rounded-xl p-5 border",
        "border-slate-200 bg-white text-slate-900",
        "dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-100",
        className,
      ].join(" ")}
    >
      {title !== null && <h2 className="text-lg font-semibold mb-4">{title}</h2>}

      <div className="space-y-3">
        <input
          className="w-full rounded-lg border px-3 py-2 outline-none focus:ring-2 focus:ring-sky-600/30 border-slate-300 bg-white text-slate-900 placeholder:text-slate-400 dark:border-slate-700 dark:bg-slate-950/30 dark:text-slate-100 dark:placeholder:text-slate-400"
          placeholder="Company name"
          value={form.company_name}
          onChange={(e) => setForm({ ...form, company_name: e.target.value })}
        />

        <input
          className="w-full rounded-lg border px-3 py-2 outline-none focus:ring-2 focus:ring-sky-600/30 border-slate-300 bg-white text-slate-900 placeholder:text-slate-400 dark:border-slate-700 dark:bg-slate-950/30 dark:text-slate-100 dark:placeholder:text-slate-400"
          placeholder="Job title"
          value={form.job_title}
          onChange={(e) => setForm({ ...form, job_title: e.target.value })}
        />

        <input
          className="w-full rounded-lg border px-3 py-2 outline-none focus:ring-2 focus:ring-sky-600/30 border-slate-300 bg-white text-slate-900 placeholder:text-slate-400 dark:border-slate-700 dark:bg-slate-950/30 dark:text-slate-100 dark:placeholder:text-slate-400"
          placeholder="Location (optional)"
          value={form.location}
          onChange={(e) => setForm({ ...form, location: e.target.value })}
        />

        <input
          className="w-full rounded-lg border px-3 py-2 outline-none focus:ring-2 focus:ring-sky-600/30 border-slate-300 bg-white text-slate-900 placeholder:text-slate-400 dark:border-slate-700 dark:bg-slate-950/30 dark:text-slate-100 dark:placeholder:text-slate-400"
          placeholder="Job URL (optional)"
          value={form.job_url}
          onChange={(e) => setForm({ ...form, job_url: e.target.value })}
        />

        <button
          type="submit"
          className={[
            "w-full rounded-lg px-4 py-2 font-semibold transition border",
            "border-slate-300 bg-slate-900 text-white hover:bg-slate-800",
            "dark:border-slate-700 dark:bg-slate-800/70 dark:text-slate-100 dark:hover:bg-slate-800",
          ].join(" ")}
        >
          Create Job
        </button>
      </div>
    </form>
  );
}