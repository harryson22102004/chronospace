export type ProvenanceClass = "observed" | "vision_estimated" | "generative" | "human_testimony";

export type Entity = {
  id: string;
  index: number;
  label: string;
  label_origin: string;
  content_status: string;
  animation: string | null;
  classifier_note: string;
  centroid_uv: [number, number];
  median_normalized_depth: number | null;
  median_disparity: number | null;
  area_fraction: number;
  mask_url: string;
  provenance_ids: string[];
  model_native_confidence?: { value: number; origin: string; calibration_status: string } | null;
};

export type Provenance = {
  id: string;
  entity_id: string | null;
  provenance_class: ProvenanceClass;
  source_photo_id: string | null;
  source_mask_id: string | null;
  model: { id: string; provider: string; task: string } | null;
  evidence: Record<string, boolean>;
  model_native_confidence: { value: number; origin: string; calibration_status: string } | null;
  calibration_status: string;
  notes: string;
  created_at: string;
};

export type Invocation = {
  id: string;
  model_id: string;
  provider: string;
  task: string;
  status: string;
  live: boolean;
  duration_ms: number | null;
  output_summary: string;
  error: string | null;
};

export type Hypothesis = {
  id: string;
  title: string;
  claim: string;
  status: string;
  generator: { model_id: string; provider: string; live: boolean };
  prompt: string;
  conflict_note: string;
  artifact_url: string;
  speaker?: string | null;
};

export type Testimony = {
  id: string;
  text: string;
  speaker: string | null;
  source: string;
  verification: string;
  verification_note: string;
  created_at: string;
};

export type Memory = {
  id: string;
  title: string;
  created_at: string;
  sample: boolean;
  sample_note: string | null;
  photograph: {
    id: string;
    width: number;
    height: number;
    url: string;
    capture_time: string | null;
    capture_time_reliability: string;
  };
  depth: {
    model_id: string;
    note: string;
    calibration_status: string;
    duration_ms: number;
    disparity_min: number;
    disparity_max: number;
    closer: string;
  };
  segmentation: { model_id: string; note: string; live_meta: boolean };
  scene_description: { text: string; origin: string; model_id: string | null };
  audio_profile: { elements: string[]; origin: string; note: string };
  entities: Entity[];
  relationships: { id: string; type: string; source_id: string; target_id: string; status: string; note: string }[];
  provenances: Provenance[];
  testimonies: Testimony[];
  hypotheses: Hypothesis[];
  active_hypothesis_id: string | null;
  invocations: Invocation[];
  assets: Record<string, string>;
  links: {
    id: string;
    type: string;
    status: string;
    a: { memory_id: string; entity_id: string; label: string };
    b: { memory_id: string; entity_id: string; label: string };
    cues: string[];
    note: string;
  }[];
  collection_timeline?: { memory_id: string; title: string; at: string; reliability: string }[];
};

export type AgentTurn = {
  narration: string;
  commentary: string | null;
  tool_trace: { name: string; args: Record<string, unknown>; result: unknown }[];
  actions: { type: string; entity_id?: string; label?: string; uv?: [number, number]; mode?: string; claim?: string }[];
  source: { model_id: string; provider: string; live: boolean };
};
