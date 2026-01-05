import type { JobBoardCard } from "../../types/api";

export type DemoNote = {
  id: number;
  body: string;
  created_at: string;
};

export type DemoDocument = {
  id: number;
  name: string;
  status: "CLEAN" | "PENDING" | "INFECTED";
  uploaded_at: string;
};

export type DemoInterview = {
  id: number;
  stage: string;
  scheduled_at: string;
  interviewer: string;
  region?: string;
  notes?: string;
};

export type DemoActivity = {
  id: number;
  type: string;
  message: string;
  created_at: string;
};

export type DemoJobDetail = {
  id: number;
  summary: string;
  job_url?: string;
  description?: string;
  location?: string;
  notes: DemoNote[];
  documents: DemoDocument[];
  interviews: DemoInterview[];
  activity: DemoActivity[];
};

export type DemoData = {
  cards: JobBoardCard[];
  details: Record<number, DemoJobDetail>;
  statuses: string[];
};

const STATUSES = ["applied", "recruiter_screen", "interviewing", "offer", "accepted", "archived"] as const;

type TimeHelpers = {
  daysAgo: (days: number) => string;
  daysAhead: (days: number) => string;
};

const makeTimeHelpers = (base: Date): TimeHelpers => {
  const msInDay = 24 * 60 * 60 * 1000;
  return {
    daysAgo: (n: number) => new Date(base.getTime() - n * msInDay).toISOString(),
    daysAhead: (n: number) => new Date(base.getTime() + n * msInDay).toISOString(),
  };
};

export function createDemoData(now: Date = new Date()): DemoData {
  const { daysAgo, daysAhead } = makeTimeHelpers(now);

  const cards: JobBoardCard[] = [
    {
      id: 101,
      status: "applied",
      company_name: "Arcade AI",
      job_title: "Product Designer",
      location: "Remote — US",
      updated_at: daysAgo(1),
      last_activity_at: daysAgo(1),
      last_action_at: daysAgo(2),
      next_action_at: daysAhead(1),
      next_action_title: "Nudge recruiter",
      priority: "high",
      tags: ["Design system", "Series B"],
      needs_follow_up: true,
    },
    {
      id: 102,
      status: "recruiter_screen",
      company_name: "Verdant Ops",
      job_title: "Senior Operations Manager",
      location: "Austin, TX",
      updated_at: daysAgo(0),
      last_activity_at: daysAgo(0),
      last_action_at: daysAgo(1),
      next_action_at: daysAhead(3),
      next_action_title: "Prep growth story",
      priority: "normal",
      tags: ["Operations"],
      needs_follow_up: false,
    },
    {
      id: 103,
      status: "interviewing",
      company_name: "Northwind Labs",
      job_title: "Head of GTM",
      location: "New York, NY",
      updated_at: daysAgo(0),
      last_activity_at: daysAgo(0),
      last_action_at: daysAgo(0),
      next_action_at: daysAhead(2),
      next_action_title: "Panel interview",
      priority: "high",
      tags: ["GTM", "Hybrid"],
      needs_follow_up: false,
    },
    {
      id: 104,
      status: "offer",
      company_name: "Calico Robotics",
      job_title: "Program Manager",
      location: "Seattle, WA",
      updated_at: daysAgo(0),
      last_activity_at: daysAgo(0),
      last_action_at: daysAgo(0),
      next_action_at: daysAhead(4),
      next_action_title: "Offer review",
      priority: "normal",
      tags: ["Robotics"],
      needs_follow_up: false,
    },
    {
      id: 105,
      status: "accepted",
      company_name: "SignalBeam",
      job_title: "Lead Customer Success",
      location: "Remote",
      updated_at: daysAgo(5),
      last_activity_at: daysAgo(5),
      last_action_at: daysAgo(6),
      next_action_at: null,
      next_action_title: null,
      priority: "low",
      tags: ["CS"],
      needs_follow_up: false,
    },
  ];

  const baseNotes: DemoNote[] = [
    { id: 1, body: "Warm intro via alumni Slack. Sent tailored case study.", created_at: daysAgo(3) },
    { id: 2, body: "Recruiter asked for portfolio updates.", created_at: daysAgo(2) },
  ];

  const baseActivity: DemoActivity[] = [
    { id: 1, type: "application_submitted", message: "Application submitted via Lever", created_at: daysAgo(5) },
    { id: 2, type: "note_added", message: "Added note: Warm intro via alumni Slack.", created_at: daysAgo(3) },
    { id: 3, type: "status_changed", message: "Status moved to Interviewing", created_at: daysAgo(1) },
  ];

  const baseDocuments: DemoDocument[] = [
    { id: 1, name: "Resume.pdf", status: "CLEAN", uploaded_at: daysAgo(5) },
    { id: 2, name: "Portfolio-links.txt", status: "CLEAN", uploaded_at: daysAgo(4) },
  ];

  const baseInterviews: DemoInterview[] = [
    {
      id: 1,
      stage: "Recruiter screen",
      scheduled_at: daysAgo(1),
      interviewer: "Avery Hart",
      notes: "Intro call focused on storytelling.",
    },
    {
      id: 2,
      stage: "Panel",
      scheduled_at: daysAhead(2),
      interviewer: "GTM Leadership",
      notes: "Prepare 30/60/90 plan.",
    },
  ];

  const details: Record<number, DemoJobDetail> = {
    101: {
      id: 101,
      summary: "Product Designer owning design system + prototyping at Series B AI productivity startup.",
      job_url: "https://careers.arcade.ai/product-designer",
      description: "Partner with PM + Eng to ship dopamine-friendly focus tools used by 1M+ users. Expect quick iteration loops.",
      notes: baseNotes,
      documents: baseDocuments,
      interviews: baseInterviews,
      activity: baseActivity,
    },
    102: {
      id: 102,
      summary: "Ops leader building onboarding playbooks for a rapidly scaling logistics platform.",
      job_url: "https://jobs.verdantops.com/ops-manager",
      description: "Drive cross-functional programs across GTM + Ops, instrument ‘next action’ cadences for 40+ program managers.",
      notes: [{ id: 5, body: "COO loves momentum dashboard idea. Send Loom by Friday.", created_at: daysAgo(1) }],
      documents: baseDocuments,
      interviews: [
        baseInterviews[0],
        {
          id: 6,
          stage: "Founder chat",
          scheduled_at: daysAhead(3),
          interviewer: "Priya Dhawan",
          notes: "Focus on KPI instrumentation story.",
        },
      ],
      activity: baseActivity,
    },
    103: {
      id: 103,
      summary: "Head of GTM leading PLG + enterprise overlay for collaborative analytics company.",
      job_url: "https://northwindlabs.com/careers/head-of-gtm",
      description: "Own revenue playbooks, manage 4 pod leads, align board on momentum metrics, and unblock enterprise pilots.",
      notes: [
        { id: 9, body: "Need executive summary for CFO by Monday.", created_at: daysAgo(0) },
        { id: 10, body: "Panel will include CRO, CMO, VP CS.", created_at: daysAgo(1) },
      ],
      documents: [
        { id: 10, name: "GTM-Case-Study.pdf", status: "CLEAN", uploaded_at: daysAgo(2) },
        { id: 11, name: "Reference-list.docx", status: "PENDING", uploaded_at: daysAgo(0) },
      ],
      interviews: [
        {
          id: 9,
          stage: "Panel interview",
          scheduled_at: daysAhead(2),
          interviewer: "Panel",
          notes: "60-min presentation + Q&A.",
        },
        {
          id: 10,
          stage: "Founder sync",
          scheduled_at: daysAhead(4),
          interviewer: "CEO",
          notes: "Discuss GTM health metrics + next 90 days.",
        },
      ],
      activity: [
        { id: 20, type: "note_added", message: "Added note: Panel will include CRO, CMO, VP CS.", created_at: daysAgo(1) },
        { id: 21, type: "document_uploaded", message: "Uploaded GTM case study.", created_at: daysAgo(2) },
        { id: 22, type: "status_changed", message: "Status moved to Interviewing.", created_at: daysAgo(3) },
      ],
    },
    104: {
      id: 104,
      summary: "Program Manager orchestrating hardware + software launches for humanoid robotics startup.",
      job_url: "https://calicorobotics.com/careers/program-manager",
      description: "Lead cross-functional launch pods, align suppliers, and keep investor updates crisp. Heavy async coordination.",
      notes: [{ id: 30, body: "Offer call on Thursday. Need comp breakdown.", created_at: daysAgo(0) }],
      documents: [{ id: 31, name: "Offer-letter.pdf", status: "CLEAN", uploaded_at: daysAgo(0) }],
      interviews: [
        {
          id: 31,
          stage: "Offer review",
          scheduled_at: daysAhead(1),
          interviewer: "People Ops",
          notes: "Deep dive on equity refresh.",
        },
      ],
      activity: [
        { id: 40, type: "offer_received", message: "Offer received from Calico Robotics.", created_at: daysAgo(1) },
        { id: 41, type: "note_added", message: "Added note: Need comp breakdown.", created_at: daysAgo(0) },
      ],
    },
    105: {
      id: 105,
      summary: "Customer success lead spinning up enterprise playbooks.",
      job_url: "https://signalbeam.io/careers/cs-lead",
      description: "Own lighthouse accounts, build renewal predictors, and mentor CSMs. Offer accepted; onboarding mid-February.",
      notes: [{ id: 50, body: "Accepted offer. Need to send signed paperwork.", created_at: daysAgo(5) }],
      documents: [{ id: 51, name: "Signed-offer.pdf", status: "CLEAN", uploaded_at: daysAgo(5) }],
      interviews: [],
      activity: [{ id: 60, type: "status_changed", message: "Status moved to Accepted.", created_at: daysAgo(5) }],
    },
  };

  return {
    cards,
    details,
    statuses: [...STATUSES],
  };
}
