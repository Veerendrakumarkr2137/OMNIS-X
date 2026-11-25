export type User = {
  id: string;
  name: string;
  role: "Admin" | "HOD" | "Faculty" | "Student" | "Operator";
  dept: string | null;
  resource: string | null;
};
export type Resource = {
  id: string;
  name: string;
  kind: string;
  dept: string | null;
  details: {
    capacity?: number;
    building?: string;
    equipment?: string[];
    subjects?: string[];
    size?: number;
    limit?: number;
    consecutive?: number;
    available?: number[];
  };
};
export type Slot = { start: number; faculty: string; room: string };
export type Lesson = Slot & {
  id: string;
  day: string;
  subject: string;
  dept: string;
  cohort: string;
  duration: number;
  kind: string;
  status: string;
  previous: Slot | null;
};
export type Impact = {
  solver_status?: string;
  sessions: string[];
  students: number;
  exams: number;
  cohorts: string[];
  depths: Record<string, number>;
  minutes: number;
};
export type Incident = {
  id: number;
  title: string;
  roots: string[];
  start: number;
  end: number;
  day: string;
  impact: Impact;
  severity: string;
  status: string;
  reason?: string;
  simulation: boolean;
  created: string;
};
export type Change = {
  id: string;
  subject: string;
  cohort: string;
  before: Slot;
  after: Slot | null;
  duration: number;
};
export type Plan = {
  id: number;
  rank: number;
  revision: number;
  case_id: number;
  status: string;
  data: {
    changes: Change[];
    recovered: number;
    unresolved: number;
    students: number;
    delay: number;
    rooms: number;
    subs: number;
    penalty: number;
    solver: string;
    outcome: string;
    violations: number;
    explanation: string;
    blockers: { session: string; reason: string }[];
  };
};
export type Notice = {
  id: number;
  title: string;
  message: string;
  route: string;
  created: string;
  seen: boolean;
};
export type Dashboard = {
  anchor: string;
  version: number;
  revision: number;
  mode: string;
  hod_approval: boolean;
  require_consent?: boolean;
  score?: number;
  risks?: { title: string; detail: string; severity: string }[];
  factors?: Record<string, number | null>;
};
export type Policy = {
  mode: string;
  hod_approval: boolean;
  require_consent?: boolean;
  delay_weight: number;
  room_weight: number;
  faculty_weight: number;
  travel_minutes: number;
  auto_penalty_limit: number;
};
export type Audit = {
  id: number;
  actor: string;
  action: string;
  created: string;
};
export type Twin = {
  nodes: Resource[];
  edges: { source: string; target: string; rule: string }[];
};
export type Campus = {
  user: User;
  dash: Dashboard;
  resources: Resource[];
  lessons: Lesson[];
  cases: Incident[];
  plans: Plan[];
  notices: Notice[];
  refresh: () => Promise<void>;
  name: (id: string) => string;
};
export const time = (n: number) =>
  String(Math.floor(n / 60)).padStart(2, "0") +
  ":" +
  String(n % 60).padStart(2, "0");
export const pretty = (s: string) =>
  new Date(s + "T12:00:00").toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
export const fromTime = (s: string) =>
  Number(s.slice(0, 2)) * 60 + Number(s.slice(3));
export const privileged = (u: User) =>
  ["Admin", "HOD", "Operator"].includes(u.role);
