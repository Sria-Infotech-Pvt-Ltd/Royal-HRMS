export type FeedbackRecommendation = "recommend" | "hold" | "not_recommend";

export interface FeedbackEntry {
  id: string;
  interviewer: string;
  rating: number;
  recommendation: FeedbackRecommendation;
  recommendation_label: string;
  comments: string;
  submitted_at: string;
  updated_at: string;
}

export interface FeedbackSummary {
  count: number;
  average_rating: number | null;
  recommend: number;
  undecided: number;
  not_recommend: number;
}

export interface CandidateFeedbackData {
  candidate: { id: number; name: string; status: string; status_label: string };
  summary: FeedbackSummary;
  feedback: FeedbackEntry[];
}

export interface MyInterview {
  id: number;
  candidate_name: string;
  position_applied: string;
  branch: string;
  interview_date: string | null;
  interview_time: string | null;
  interview_mode: string;
  interview_mode_label: string;
  meeting_link: string;
  status: string;
  status_label: string;
  can_submit: boolean;
  my_feedback: FeedbackEntry | null;
}

export interface FeedbackInput {
  rating: number;
  recommendation: FeedbackRecommendation;
  comments: string;
}
