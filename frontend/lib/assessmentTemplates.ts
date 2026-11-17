// Starting points for a new assessment. A template only pre-fills the title and description of the form; the pass mark, attempts
// and time limit still come from Settings → Assessment Config, and the sections (videos / questions) are added afterwards.

export interface AssessmentTemplate {
  id:          "quiz" | "video" | "mixed" | "blank"
  title:       string
  /** What the card says this type is for. */
  summary:     string
  /** What the person will add once it is created. */
  contains:    string
  icon:        string
  tone:        "primary" | "info" | "success" | "neutral"
  /** Pre-filled into the form; empty for a blank start. */
  formTitle:   string
  formDescription: string
}

export const ASSESSMENT_TEMPLATES: AssessmentTemplate[] = [
  {
    id: "quiz", title: "Knowledge quiz", icon: "ti-help-circle", tone: "primary",
    summary: "Check that people understood a policy, process or training.",
    contains: "Quiz questions",
    formTitle: "Knowledge Quiz", formDescription: "Questions to check understanding before the person starts.",
  },
  {
    id: "video", title: "Video training", icon: "ti-player-play", tone: "info",
    summary: "Have people watch training videos, with no questions.",
    contains: "Videos to watch",
    formTitle: "Video Training", formDescription: "Training videos to watch before the person starts.",
  },
  {
    id: "mixed", title: "Video + quiz", icon: "ti-school", tone: "success",
    summary: "Watch the training first, then answer questions on it.",
    contains: "Videos and quiz questions",
    formTitle: "Training and Quiz", formDescription: "Watch the training, then answer questions to confirm understanding.",
  },
  {
    id: "blank", title: "Start from scratch", icon: "ti-file-plus", tone: "neutral",
    summary: "An empty assessment: set everything up yourself.",
    contains: "Anything you choose",
    formTitle: "", formDescription: "",
  },
]

export function templateById(id: string): AssessmentTemplate | undefined {
  return ASSESSMENT_TEMPLATES.find(template => template.id === id)
}
