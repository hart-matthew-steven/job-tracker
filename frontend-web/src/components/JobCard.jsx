export default function JobCard({ form, setForm, onCreateJob }) {
  return (
    <form
      onSubmit={onCreateJob}
      className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 mb-6"
    >
      <h2 className="text-lg font-semibold mb-4">Add Job</h2>

      <div className="space-y-3">
        <input
          className="w-full rounded-lg bg-slate-800/70 border border-slate-700 px-3 py-2 outline-none focus:ring-2 focus:ring-slate-500"
          placeholder="Company name"
          value={form.company_name}
          onChange={(e) => setForm({ ...form, company_name: e.target.value })}
        />

        <input
          className="w-full rounded-lg bg-slate-800/70 border border-slate-700 px-3 py-2 outline-none focus:ring-2 focus:ring-slate-500"
          placeholder="Job title"
          value={form.job_title}
          onChange={(e) => setForm({ ...form, job_title: e.target.value })}
        />

        <input
          className="w-full rounded-lg bg-slate-800/70 border border-slate-700 px-3 py-2 outline-none focus:ring-2 focus:ring-slate-500"
          placeholder="Location (optional)"
          value={form.location}
          onChange={(e) => setForm({ ...form, location: e.target.value })}
        />

        <input
          className="w-full rounded-lg bg-slate-800/70 border border-slate-700 px-3 py-2 outline-none focus:ring-2 focus:ring-slate-500"
          placeholder="Job URL (optional)"
          value={form.job_url}
          onChange={(e) => setForm({ ...form, job_url: e.target.value })}
        />

        <button
          type="submit"
          className="w-full rounded-lg bg-blue-600 hover:bg-blue-500 transition px-4 py-2 font-semibold cursor-pointer"
        >
          Create Job
        </button>
      </div>
    </form>
  );
}