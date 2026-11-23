import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Download, Eye, FilePlus2, FolderPlus, Plus, Save, Trash2, Upload } from "lucide-react";
import { api } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import type { CourseDetail, CourseSummary } from "../../api/types";
import { Markdown, toast } from "../../components/ui";

type Sel = { kind: "course" } | { kind: "module"; id: string } | { kind: "lesson"; id: string } | { kind: "quiz"; id: string | null; moduleId: string } | { kind: "import" };

export default function ContentEditor() {
  const { t } = useTranslation();
  const { data: courses, reload: reloadCourses } = useApi<CourseSummary[]>("/courses?include_drafts=true");
  const [slug, setSlug] = useState<string>("");
  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [sel, setSel] = useState<Sel>({ kind: "course" });

  useEffect(() => {
    if (!slug && courses?.length) setSlug(courses[0].slug);
  }, [courses, slug]);
  const loadCourse = async () => slug && setCourse(await api(`/courses/${slug}`));
  useEffect(() => {
    loadCourse();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  const addModule = async () => {
    const r = await api("/modules", { method: "POST", json: { course_id: course!.id, title: t("admin.newModule") } });
    await loadCourse();
    setSel({ kind: "module", id: r.id });
  };
  const addLesson = async (moduleId: string) => {
    const r = await api("/lessons", { method: "POST", json: { module_id: moduleId, title: t("admin.newLesson"), content: "# " + t("admin.newLesson") } });
    await loadCourse();
    setSel({ kind: "lesson", id: r.id });
  };
  const newCourse = async () => {
    const s = prompt("slug (masalan: linux-security-advanced)");
    if (!s) return;
    await api("/courses", { method: "POST", json: { slug: s, title: s, code: "" } });
    await reloadCourses();
    setSlug(s);
  };
  const exportPack = async () => {
    const text = await api<string>(`/courses/${slug}/export`, { raw: true });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([text], { type: "text/yaml" }));
    a.download = `${slug}.yaml`;
    a.click();
  };

  return (
    <div className="grid lg:grid-cols-4 gap-5">
      <aside className="panel p-3 h-fit space-y-3">
        <div className="flex gap-2">
          <select className="input text-xs" value={slug} onChange={(e) => { setSlug(e.target.value); setSel({ kind: "course" }); }}>
            {courses?.map((c) => <option key={c.slug} value={c.slug}>{c.code} {c.title} {c.status !== "published" ? "(draft)" : ""}</option>)}
          </select>
          <button className="btn-ghost px-2" title={t("admin.newCourse")} onClick={newCourse}><Plus size={15} /></button>
        </div>
        <div className="flex gap-2">
          <button className="btn-ghost text-xs flex-1" onClick={exportPack}><Download size={13} /> YAML</button>
          <button className="btn-ghost text-xs flex-1" onClick={() => setSel({ kind: "import" })}><Upload size={13} /> YAML</button>
        </div>
        <button className={`w-full text-left text-sm px-2 py-1.5 rounded ${sel.kind === "course" ? "text-neon bg-neon/10" : "hover:bg-white/5"}`} onClick={() => setSel({ kind: "course" })}>⚙ {course?.title}</button>
        {course?.modules_detail.map((m) => (
          <div key={m.id}>
            <div className={`flex items-center justify-between px-2 py-1.5 rounded text-sm ${sel.kind === "module" && sel.id === m.id ? "text-neon bg-neon/10" : "hover:bg-white/5"}`}>
              <button className="text-left flex-1 font-mono text-xs" onClick={() => setSel({ kind: "module", id: m.id })}>
                {String(m.sequence_number).padStart(2, "0")} {m.title}
              </button>
              <button className="text-muted hover:text-neon" title={t("admin.newLesson")} onClick={() => addLesson(m.id)}><FilePlus2 size={14} /></button>
            </div>
            <div className="ml-4 border-l border-edge">
              {m.lessons.map((le) => (
                <button key={le.id} onClick={() => setSel({ kind: "lesson", id: le.id })}
                  className={`block w-full text-left text-xs px-3 py-1 ${sel.kind === "lesson" && sel.id === le.id ? "text-neon" : "text-slate-400 hover:text-slate-200"}`}>
                  {le.lesson_type === "lab" ? "⚗" : "▸"} {le.title}
                </button>
              ))}
              <button onClick={() => setSel({ kind: "quiz", id: m.quiz?.id ?? null, moduleId: m.id })}
                className={`block w-full text-left text-xs px-3 py-1 ${sel.kind === "quiz" && sel.moduleId === m.id ? "text-violet" : "text-violet/60 hover:text-violet"}`}>
                ☑ {m.quiz ? m.quiz.title : t("admin.quizEditor")}
              </button>
            </div>
          </div>
        ))}
        <button className="btn-ghost w-full text-xs" onClick={addModule} disabled={!course}><FolderPlus size={14} /> {t("admin.newModule")}</button>
      </aside>
      <div className="lg:col-span-3">
        {course && sel.kind === "course" && <CourseForm course={course} onSaved={() => { loadCourse(); reloadCourses(); }} />}
        {sel.kind === "module" && <ModuleForm key={sel.id} id={sel.id} onSaved={loadCourse} />}
        {sel.kind === "lesson" && <LessonForm key={sel.id} id={sel.id} onSaved={loadCourse} onDeleted={() => { setSel({ kind: "course" }); loadCourse(); }} />}
        {sel.kind === "quiz" && <QuizForm key={sel.moduleId} id={sel.id} moduleId={sel.moduleId} onSaved={loadCourse} />}
        {sel.kind === "import" && <ImportForm onDone={(s) => { reloadCourses(); setSlug(s); setSel({ kind: "course" }); }} />}
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><label className="label">{label}</label>{children}</div>;
}

function CourseForm({ course, onSaved }: { course: CourseDetail; onSaved: () => void }) {
  const { t } = useTranslation();
  const [f, setF] = useState({ title: course.title, code: course.code, description: course.description, difficulty: course.difficulty, status: course.status, objectives: (course.objectives ?? []).join("\n"), tr: course.translations ?? {} });
  useEffect(() => setF({ title: course.title, code: course.code, description: course.description, difficulty: course.difficulty, status: course.status, objectives: (course.objectives ?? []).join("\n"), tr: course.translations ?? {} }), [course]);
  const save = async () => {
    await api(`/courses/${course.slug}`, { method: "PUT", json: { title: f.title, code: f.code, description: f.description, difficulty: f.difficulty, status: f.status, objectives: f.objectives.split("\n").filter(Boolean), translations: f.tr } });
    toast(t("common.saved"));
    onSaved();
  };
  const del = async () => {
    if (!confirm(`${course.slug}?`)) return;
    await api(`/courses/${course.slug}`, { method: "DELETE" });
    onSaved();
  };
  return (
    <div className="panel p-5 space-y-4">
      <div className="grid md:grid-cols-4 gap-3">
        <Field label="Code"><input className="input font-mono" value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} /></Field>
        <div className="md:col-span-3"><Field label="Title (uz)"><input className="input" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field></div>
      </div>
      <Field label="Description (uz)"><textarea className="input h-20" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>
      <div className="grid md:grid-cols-2 gap-3">
        <Field label="Difficulty"><select className="input" value={f.difficulty} onChange={(e) => setF({ ...f, difficulty: e.target.value })}>{["beginner", "intermediate", "advanced"].map((x) => <option key={x}>{x}</option>)}</select></Field>
        <Field label={t("common.status")}><select className="input" value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}>{["published", "draft", "archived"].map((x) => <option key={x}>{x}</option>)}</select></Field>
      </div>
      <Field label={t("courses.objectives")}><textarea className="input h-24 font-mono text-xs" value={f.objectives} onChange={(e) => setF({ ...f, objectives: e.target.value })} /></Field>
      <div className="grid md:grid-cols-2 gap-3">
        {(["ru", "en"] as const).map((l) => (
          <div key={l} className="space-y-2 border border-edge rounded-lg p-3">
            <div className="label">{t("admin.translations")} · {l}</div>
            <input className="input" placeholder="title" value={f.tr[l]?.title ?? ""} onChange={(e) => setF({ ...f, tr: { ...f.tr, [l]: { ...f.tr[l], title: e.target.value } } })} />
            <textarea className="input h-16" placeholder="description" value={f.tr[l]?.description ?? ""} onChange={(e) => setF({ ...f, tr: { ...f.tr, [l]: { ...f.tr[l], description: e.target.value } } })} />
          </div>
        ))}
      </div>
      <div className="flex gap-2"><button className="btn-primary" onClick={save}><Save size={15} /> {t("common.save")}</button><button className="btn-danger" onClick={del}><Trash2 size={15} /></button></div>
    </div>
  );
}

function ModuleForm({ id, onSaved }: { id: string; onSaved: () => void }) {
  const { t } = useTranslation();
  const { data } = useApi<any>(`/modules/${id}`);
  const [f, setF] = useState<any>(null);
  useEffect(() => data && setF(data), [data]);
  if (!f) return null;
  const save = async () => {
    await api(`/modules/${id}`, { method: "PUT", json: { title: f.title, slug: f.slug, level: f.level, description: f.description, sequence_number: Number(f.sequence_number), translations: f.translations } });
    toast(t("common.saved"));
    onSaved();
  };
  const del = async () => {
    if (!confirm(f.title + "?")) return;
    await api(`/modules/${id}`, { method: "DELETE" });
    onSaved();
  };
  return (
    <div className="panel p-5 space-y-4">
      <div className="grid md:grid-cols-4 gap-3">
        <div className="md:col-span-2"><Field label="Title (uz)"><input className="input" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field></div>
        <Field label="Slug"><input className="input font-mono" value={f.slug} onChange={(e) => setF({ ...f, slug: e.target.value })} /></Field>
        <Field label="#"><input className="input font-mono" type="number" value={f.sequence_number} onChange={(e) => setF({ ...f, sequence_number: e.target.value })} /></Field>
      </div>
      <Field label="Level"><select className="input" value={f.level} onChange={(e) => setF({ ...f, level: e.target.value })}>{["beginner", "intermediate", "advanced"].map((x) => <option key={x}>{x}</option>)}</select></Field>
      <Field label="Description"><textarea className="input h-24" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>
      <div className="grid md:grid-cols-2 gap-3">
        {(["ru", "en"] as const).map((l) => (
          <Field key={l} label={`${t("admin.translations")} · ${l}`}>
            <input className="input" value={f.translations?.[l]?.title ?? ""} onChange={(e) => setF({ ...f, translations: { ...f.translations, [l]: { ...f.translations?.[l], title: e.target.value } } })} />
          </Field>
        ))}
      </div>
      <div className="flex gap-2"><button className="btn-primary" onClick={save}><Save size={15} /> {t("common.save")}</button><button className="btn-danger" onClick={del}><Trash2 size={15} /></button></div>
    </div>
  );
}

function LessonForm({ id, onSaved, onDeleted }: { id: string; onSaved: () => void; onDeleted: () => void }) {
  const { t } = useTranslation();
  const [f, setF] = useState<any>(null);
  const [lang, setLang] = useState<"uz" | "ru" | "en">("uz");
  const [preview, setPreview] = useState(false);
  useEffect(() => {
    api(`/lessons/${id}?lang=uz`).then((d) => setF({ ...d, title: d.original.title, content: d.original.content, translations: d.translations ?? {} }));
  }, [id]);
  if (!f) return null;
  const cur = lang === "uz" ? { title: f.title, content: f.content } : f.translations[lang] ?? { title: "", content: "" };
  const setCur = (k: "title" | "content", v: string) =>
    lang === "uz" ? setF({ ...f, [k]: v }) : setF({ ...f, translations: { ...f.translations, [lang]: { ...cur, [k]: v } } });
  const save = async () => {
    await api(`/lessons/${id}`, { method: "PUT", json: { title: f.title, content: f.content, lesson_type: f.lesson_type, duration: Number(f.duration), lab_slug: f.lab_slug || null, video_url: f.video_url || null, sequence_number: Number(f.sequence_number), translations: f.translations } });
    toast(t("common.saved"));
    onSaved();
  };
  const del = async () => {
    if (!confirm(f.title + "?")) return;
    await api(`/lessons/${id}`, { method: "DELETE" });
    onDeleted();
  };
  return (
    <div className="panel p-5 space-y-4">
      <div className="grid md:grid-cols-5 gap-3">
        <Field label="Type"><select className="input" value={f.lesson_type} onChange={(e) => setF({ ...f, lesson_type: e.target.value })}>{["theory", "video", "lab"].map((x) => <option key={x}>{x}</option>)}</select></Field>
        <Field label={t("common.minutes")}><input className="input font-mono" type="number" value={f.duration} onChange={(e) => setF({ ...f, duration: e.target.value })} /></Field>
        <Field label="#"><input className="input font-mono" type="number" value={f.sequence_number} onChange={(e) => setF({ ...f, sequence_number: e.target.value })} /></Field>
        <Field label="Lab slug"><input className="input font-mono" value={f.lab_slug ?? ""} onChange={(e) => setF({ ...f, lab_slug: e.target.value })} /></Field>
        <Field label="Video URL"><input className="input" value={f.video_url ?? ""} onChange={(e) => setF({ ...f, video_url: e.target.value })} /></Field>
      </div>
      <div className="flex items-center gap-1 border-b border-edge">
        {(["uz", "ru", "en"] as const).map((l) => <button key={l} className={`tab ${lang === l ? "tab-active" : ""}`} onClick={() => setLang(l)}>{l.toUpperCase()}</button>)}
        <button className="ml-auto btn-ghost text-xs py-1" onClick={() => setPreview(!preview)}><Eye size={13} /> {t("admin.preview")}</button>
      </div>
      <Field label="Title"><input className="input" value={cur.title} onChange={(e) => setCur("title", e.target.value)} /></Field>
      <div className={`grid gap-3 ${preview ? "md:grid-cols-2" : ""}`}>
        <textarea spellCheck={false} className="input h-[440px] font-mono text-[13px]" value={cur.content} onChange={(e) => setCur("content", e.target.value)} placeholder="Markdown…" />
        {preview && <div className="border border-edge rounded-lg p-4 h-[440px] overflow-y-auto"><Markdown text={cur.content} /></div>}
      </div>
      <div className="flex gap-2"><button className="btn-primary" onClick={save}><Save size={15} /> {t("common.save")}</button><button className="btn-danger" onClick={del}><Trash2 size={15} /></button></div>
    </div>
  );
}

type QQ = { text: string; type: string; difficulty: string; options: string[]; correct: number[] };

function QuizForm({ id, moduleId, onSaved }: { id: string | null; moduleId: string; onSaved: () => void }) {
  const { t } = useTranslation();
  const [f, setF] = useState<{ title: string; passing_score: number; questions: QQ[] }>({ title: "Test", passing_score: 70, questions: [] });
  useEffect(() => {
    if (id) api(`/quizzes/${id}/edit`).then(setF);
  }, [id]);
  const upd = (i: number, q: Partial<QQ>) => setF({ ...f, questions: f.questions.map((x, j) => (j === i ? { ...x, ...q } : x)) });
  const save = async () => {
    try {
      await api(id ? `/quizzes/${id}` : "/quizzes", { method: id ? "PUT" : "POST", json: { ...f, module_id: moduleId } });
      toast(t("common.saved"));
      onSaved();
    } catch (e: any) {
      toast(e.message, "err");
    }
  };
  return (
    <div className="panel p-5 space-y-4">
      <div className="grid md:grid-cols-4 gap-3">
        <div className="md:col-span-3"><Field label="Title"><input className="input" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field></div>
        <Field label="Pass %"><input className="input font-mono" type="number" value={f.passing_score} onChange={(e) => setF({ ...f, passing_score: Number(e.target.value) })} /></Field>
      </div>
      {f.questions.map((q, i) => (
        <div key={i} className="border border-edge rounded-lg p-4 space-y-2">
          <div className="flex gap-2">
            <span className="font-mono text-cyber pt-2">{i + 1}.</span>
            <input className="input" value={q.text} onChange={(e) => upd(i, { text: e.target.value })} />
            <select className="input w-32" value={q.type} onChange={(e) => upd(i, { type: e.target.value })}><option>single</option><option>multiple</option></select>
            <button className="btn-danger px-2" onClick={() => setF({ ...f, questions: f.questions.filter((_, j) => j !== i) })}><Trash2 size={14} /></button>
          </div>
          {q.options.map((o, oi) => (
            <div key={oi} className="flex gap-2 ml-6 items-center">
              <input type="checkbox" className="accent-[#00ff9c]" checked={q.correct.includes(oi)}
                onChange={(e) => upd(i, { correct: e.target.checked ? (q.type === "single" ? [oi] : [...q.correct, oi]) : q.correct.filter((x) => x !== oi) })} />
              <input className="input py-1 text-sm" value={o} onChange={(e) => upd(i, { options: q.options.map((x, k) => (k === oi ? e.target.value : x)) })} />
              <button className="text-muted hover:text-threat" onClick={() => upd(i, { options: q.options.filter((_, k) => k !== oi), correct: q.correct.filter((x) => x !== oi).map((x) => (x > oi ? x - 1 : x)) })}>✕</button>
            </div>
          ))}
          <button className="text-xs text-cyber ml-6" onClick={() => upd(i, { options: [...q.options, ""] })}>+ option</button>
        </div>
      ))}
      <div className="flex gap-2">
        <button className="btn-ghost" onClick={() => setF({ ...f, questions: [...f.questions, { text: "", type: "single", difficulty: "beginner", options: ["", ""], correct: [0] }] })}><Plus size={15} /> {t("admin.addQuestion")}</button>
        <button className="btn-primary" onClick={save}><Save size={15} /> {t("common.save")}</button>
      </div>
    </div>
  );
}

function ImportForm({ onDone }: { onDone: (slug: string) => void }) {
  const { t } = useTranslation();
  const [text, setText] = useState("");
  const go = async () => {
    try {
      const r = await api("/courses/import", { method: "POST", json: { yaml: text, replace: true } });
      toast(t("common.saved"));
      onDone(r.slug);
    } catch (e: any) {
      toast(e.message, "err");
    }
  };
  return (
    <div className="panel p-5 space-y-3">
      <div className="label">{t("admin.importPack")}</div>
      <input type="file" accept=".yaml,.yml" className="text-sm" onChange={async (e) => e.target.files?.[0] && setText(await e.target.files[0].text())} />
      <textarea className="input h-96 font-mono text-xs" value={text} onChange={(e) => setText(e.target.value)} placeholder={"course:\n  slug: ...\nmodules:\n  - title: ..."} />
      <button className="btn-primary" disabled={!text} onClick={go}><Upload size={15} /> Import</button>
    </div>
  );
}
