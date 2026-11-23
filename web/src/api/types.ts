export type User = {
  id: string; username: string; email: string; full_name: string; preferred_language: string;
  xp: number; level: number; roles: string[]; permissions: string[]; organization_id: string | null;
};

export type CourseSummary = {
  id: string; slug: string; code: string; title: string; description: string; difficulty: string; status: string;
  estimated_duration: number; category: string | null; modules: number; lessons: number; labs: number; progress: number;
};

export type LessonRef = {
  id: string; slug: string; title: string; lesson_type: string; duration: number; lab_slug: string | null;
  completed: boolean; sequence_number: number;
};

export type ModuleDetail = {
  id: string; slug: string; title: string; level: string; description: string; sequence_number: number;
  quiz: { id: string; title: string; questions: number } | null; lessons: LessonRef[];
};

export type CourseDetail = CourseSummary & {
  objectives: string[]; enrolled: boolean; modules_detail: ModuleDetail[]; translations: Record<string, any>;
};

export type LabSummary = {
  id: string; title: string; description: string; category: string; course: string | null; lab_type: string;
  difficulty: string; duration_minutes: number; machines: number; tasks: number; points: number; version: number;
  active_instance: { id: string; status: string } | null;
};

export type LabTask = {
  id: string; title: string; description: string; hint: string | null; points: number; validation_type: string;
  input: "text" | "ports" | "hosts" | "none"; machine: string | null;
};

export type Machine = {
  id: string; name: string; role: string; status: string; os: string; ips: Record<string, string>;
  cpu: number; ram: number; snapshots: string[];
  metrics?: { cpu_percent: number; ram_used_mb: number; ram_limit_mb: number } | null; console?: boolean;
};

export type Instance = {
  id: string; lab: string; instance_name: string; provider: string; status: string; error: string | null;
  score: number; user_id: string; started_at: string | null; expires_at: string | null;
  networks: { name: string; cidr: string; type: string; policy: string }[];
  machines: Machine[]; tasks: Record<string, { score: number; passed: boolean; feedback: string }>;
};

export type LabDetail = {
  id: string; title: string; description: string; category: string; lab_type: string; difficulty: string;
  duration_minutes: number; objectives: string[]; instructions: string;
  machines: { name: string; template: string; role: string }[];
  networks: { name: string; type: string; internet: boolean }[];
  scoring: { maximum: number; passing: number; xp: number }; tasks: LabTask[]; version: number;
  scan_profiles: string[]; instance: Instance | null;
};

export type Port = { port: number; protocol: string; service: string; product?: string; version?: string };

export type TopoNode = {
  id: string; type: "internet" | "network" | "host"; label: string; cidr?: string; policy?: string; blocked?: boolean;
  role?: string; ips?: Record<string, string>; os?: string | null; status?: string; ports?: Port[];
  discovered?: boolean; you?: boolean;
};
export type TopoEdge = { source: string; target: string; blocked?: boolean };
export type Topology = { nodes: TopoNode[]; edges: TopoEdge[]; discovered_hosts: number };
