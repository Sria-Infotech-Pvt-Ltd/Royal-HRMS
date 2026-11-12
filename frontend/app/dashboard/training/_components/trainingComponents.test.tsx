import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import type { AssignmentRow, Course, Material, MyTraining } from "@/lib/training";

const fetched: Record<string, unknown> = {};
vi.mock("@/hooks/useFetch", () => ({
  useFetch: (url: string | null) => {
    const key = url ? Object.keys(fetched).sort((a, b) => b.length - a.length).find(k => url.startsWith(k)) : undefined;
    return { data: key ? fetched[key] : null, loading: false, error: null, status: null, refetch: () => {} };
  },
}));
const perms = new Set<string>();
vi.mock("@/hooks/usePermission", () => ({
  usePermission: (p: string) => perms.has(p),
  useAnyPermission: (...p: string[]) => p.some(x => perms.has(x)),
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {} }) }));
// Components report results with top-right toasts (components/ToastProvider).
vi.mock("@/components/ToastProvider", () => ({ useToast: () => ({ showToast: () => {} }) }));
vi.mock("@/lib/clientApi", () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }));

import { CourseTable, ProgressTable } from "./TrainingTables";
import TrainingPage from "../page";
import MaterialsEditor from "./MaterialsEditor";
import CourseDetailsForm from "./CourseDetailsForm";
import MyLearningPage from "@/app/dashboard/my-learning/page";
import MaterialViewer from "@/app/dashboard/my-learning/_components/MaterialViewer";
import AssessmentPanel from "@/app/dashboard/my-learning/_components/AssessmentPanel";
import { buildNav } from "@/lib/navConfig";
import { moduleForPath } from "@/lib/modules";

const person = { id: "e1", name: "Asha", employee_id: "E1", branch: "North", department: "Sales" };
const course = (over: Partial<Course> = {}): Course => ({
  id: "c1", title: "Safety Basics", description: "", category: "Safety", owner: null, trainer_name: "",
  has_thumbnail: false, duration_minutes: 30, is_mandatory: true, is_active: true, start_date: null, deadline: null,
  assessment: null, auto_assign_new_joiners: false, new_joiner_deadline_days: 30, new_joiner_branches: [],
  new_joiner_departments: [], archived: false, created_at: "2026-11-01", assigned_count: 4, completed_count: 1,
  material_count: 2, materials: [], ...over,
});
const material = (over: Partial<Material> = {}): Material => ({
  id: "m1", title: "Handbook", description: "", material_type: "document", order: 1, is_required: true,
  file_format: "pdf", file_size: 2048, original_name: "h.pdf", provider: "", embed_id: "", external_url: "",
  duration_seconds: null, min_view_seconds: 0, allow_manual_completion: false, is_tracked: false, is_archived: false,
  progress: null, ...over,
});
const row = (over: Partial<AssignmentRow> = {}): AssignmentRow => ({
  id: "a1", employee: person, course_id: "c1", course_title: "Safety Basics", status: "overdue", source: "individual",
  due_date: "2026-11-01", assigned_at: "2026-10-01", started_at: null, completed_at: null, attempts_used: 0,
  best_score_percent: null, assessment_passed: null, progress_percent: 50, ...over,
});

beforeEach(() => {
  for (const k of Object.keys(fetched)) delete fetched[k];
  perms.clear();
});

describe("navigation and routing", () => {
  it("shows Training & Learning only with permission and module", () => {
    const ids = (p: string[], m?: string[]) => buildNav(p, m).filter(e => "id" in e).map(e => (e as { id: string }).id);
    expect(ids(["training.view"], ["training"])).toContain("training");
    expect(ids([], ["training"])).not.toContain("training");
    expect(ids([], ["training"])).toContain("my-learning");
    expect(ids(["training.view"], ["attendance"])).not.toContain("training");
    expect(ids(["training.view"], ["attendance"])).not.toContain("my-learning");
    expect(moduleForPath("/dashboard/training/abc")).toBe("training");
    expect(moduleForPath("/dashboard/my-learning/abc")).toBe("training");
  });
});

describe("HR tables and pages", () => {
  it("lists courses and progress with statuses", () => {
    const html = renderToStaticMarkup(<CourseTable courses={[course(), course({ id: "c2", title: "Old", archived: true })]} onOpen={() => {}} />);
    expect(html).toContain("Safety Basics");
    expect(html).toContain("Mandatory");
    expect(html).toContain("Archived");
    const p = renderToStaticMarkup(<ProgressTable rows={[row(), row({ id: "a2", status: "completed", best_score_percent: 80 })]} showCourse />);
    expect(p).toContain("Overdue");
    expect(p).toContain("80%");
    expect(p).toContain("Sales");
  });

  it("hides create and reports without permission", () => {
    fetched["/training/courses/"] = [course()];
    let html = renderToStaticMarkup(<TrainingPage />);
    expect(html).not.toContain("New Course");
    expect(html).not.toContain("Reports");
    perms.add("training.create").add("training.view_reports");
    html = renderToStaticMarkup(<TrainingPage />);
    expect(html).toContain("New Course");
    expect(html).toContain("Reports");
  });

  it("materials editor is read-only without edit", () => {
    const c = course({ materials: [material(), material({ id: "m2", title: "Talk", material_type: "external_video",
                                                          provider: "vimeo", embed_id: "1" })] });
    const ro = renderToStaticMarkup(<MaterialsEditor course={c} canEdit={false} onChanged={() => {}} />);
    expect(ro).toContain("Handbook");
    expect(ro).not.toContain("Add learning material");
    const rw = renderToStaticMarkup(<MaterialsEditor course={c} canEdit onChanged={() => {}} />);
    expect(rw).toContain("Add learning material");
    expect(rw).toContain("Allow confirmation");                 // untrackable Vimeo
    expect(rw).toContain("Required — must be read to complete the course");
  });

  it("relabels Required, flags missing video length and honours optional videos", () => {
    const vid = material({ id: "m3", title: "Clip", material_type: "video", is_tracked: true, duration_seconds: null });
    const withQuiz = course({ materials: [material(), vid], assessment: { id: "q", title: "Quiz", pass_percentage: 60 } });
    const html = renderToStaticMarkup(<MaterialsEditor course={withQuiz} canEdit onChanged={() => {}} />);
    expect(html).toContain("Required — must be read before the assessment");
    expect(html).toContain("Required — must be watched before the assessment");
    expect(html).toContain("Set video length");
    const optional = renderToStaticMarkup(<MaterialsEditor course={{ ...withQuiz, videos_optional: true }} canEdit
                                                           onChanged={() => {}} />);
    expect(optional).toContain("Optional (course setting)");
    expect(optional).not.toContain("must be watched before the assessment");
  });

  it("course details offer the optional video watching setting", () => {
    const html = renderToStaticMarkup(<CourseDetailsForm course={course()} canEdit onSaved={() => {}} />);
    expect(html).toContain("Video watching optional");
    const past = renderToStaticMarkup(<CourseDetailsForm course={course({ deadline: "2020-01-01" })} canEdit
                                                         onSaved={() => {}} />);
    expect(past).toContain("This deadline has passed");
  });

  it("only offers assessments to users who may link them", () => {
    fetched["/training/assessments/"] = [{ id: "as1", title: "Safety quiz", questions: 5, pass_percentage: 70 }];
    let html = renderToStaticMarkup(<CourseDetailsForm course={course()} canEdit onSaved={() => {}} />);
    expect(html).not.toContain("Safety quiz");
    perms.add("training.manage_assessments");
    html = renderToStaticMarkup(<CourseDetailsForm course={course()} canEdit onSaved={() => {}} />);
    expect(html).toContain("Safety quiz (5 questions, pass 70%)");
    expect(html).toContain("does not affect onboarding assessments");
  });
});

describe("employee learning", () => {
  it("lists my courses with progress", () => {
    const mine: MyTraining = { ...row({ status: "in_progress" }), progress_percent: 50, material_count: 2, course: course() };
    fetched["/training/my/"] = [mine];
    const html = renderToStaticMarkup(<MyLearningPage />);
    expect(html).toContain("Safety Basics");
    expect(html).toContain("In Progress");
    expect(html).toContain("50% of required materials");
    fetched["/training/my/"] = [];
    expect(renderToStaticMarkup(<MyLearningPage />)).toContain("No training has been assigned to you yet.");
    fetched["/training/my/"] = [{ ...mine, starts_on: "2026-12-05" }];
    expect(renderToStaticMarkup(<MyLearningPage />)).toContain("Starts 05 Dec 2026");
  });

  it("loads PDFs through the access-checked API and offers a download for PowerPoint", () => {
    const pdf = renderToStaticMarkup(<MaterialViewer assignmentId="a1" material={material()} disabled={false} onProgress={() => {}} />);
    expect(pdf).toContain("Loading document");                           // fetched as a blob, not framed directly
    expect(pdf).not.toContain("<iframe");
    expect(pdf).not.toContain("I have read this");                       // not opened yet
    const opened = material({ progress: { opened_at: new Date().toISOString(), watched_seconds: 0, last_position_seconds: 0,
                                          duration_seconds: null, completed_at: null, completion_method: "" } });
    expect(renderToStaticMarkup(<MaterialViewer assignmentId="a1" material={opened} disabled={false} onProgress={() => {}} />))
      .toContain("I have read this");
    const pptx = renderToStaticMarkup(<MaterialViewer assignmentId="a1" material={material({ file_format: "pptx" })}
                                                      disabled={false} onProgress={() => {}} />);
    expect(pptx).toContain("Download");
    expect(pptx).toContain('href="/api/training/materials/m1/file/"');
  });

  it("embeds external videos with a fallback link", () => {
    const vimeo = renderToStaticMarkup(<MaterialViewer assignmentId="a1" material={material({
      material_type: "external_video", provider: "vimeo", embed_id: "42", external_url: "https://vimeo.com/42" })}
      disabled={false} onProgress={() => {}} />);
    expect(vimeo).toContain("player.vimeo.com/video/42");
    expect(vimeo).toContain("Open the original");
    expect(vimeo).toContain("ask HR");
  });

  it("assessment panel reflects lock, attempts and pass", () => {
    const base = { required: true, title: "Safety quiz", pass_percentage: 60, max_attempts: 2, attempts_used: 0,
                   time_limit_mins: null, best_score_percent: null, last_result: null };
    const render = (s: object) => renderToStaticMarkup(<AssessmentPanel assignmentId="a1" state={{ ...base, ...s }} onDone={() => {}} />);
    expect(render({ unlocked: false, can_attempt: false })).toContain("Complete the required learning materials");
    expect(render({ unlocked: true, can_attempt: true })).toContain("Start assessment");
    expect(render({ unlocked: true, can_attempt: false, attempts_used: 2 })).toContain("No attempts left");
    const done = render({ unlocked: true, can_attempt: false, passed: true, best_score_percent: 80 });
    expect(done).toContain("best score <strong>80%</strong>");
    expect(done).not.toContain("Retake to improve score");
    const retake = render({ unlocked: true, can_attempt: true, can_retake: true, passed: true, best_score_percent: 67,
                            attempts_used: 1, attempts_left: 1 });
    expect(retake).toContain("Retake to improve score");
    expect(retake).toContain("1 retake left");
    expect(retake).toContain("Your best score is kept and the course stays completed");
    expect(render({ unlocked: true, can_attempt: true })).toContain("Pass mark 60% · 0 of 2 attempts used");
    const empty = render({ unlocked: true, can_attempt: false, has_questions: false });
    expect(empty).toContain("This assessment has no questions yet");
    expect(empty).not.toContain("Start assessment");
    expect(empty).not.toContain("No attempts left");
  });
});
