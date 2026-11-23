"use client";

// Shows one learning material and reports progress to the API:
//  * uploaded / direct-link video: <video>, playback position every 10 s while playing
//  * YouTube: the YouTube IFrame player API, same 10 s reports
//  * Vimeo: embedded; completion only by confirmation when HR allows it
//  * PDF: shown inline; PowerPoint / Word: downloaded; then "I have read this"
// Opening a material never completes it — the server decides completion.

import { useCallback, useEffect, useRef, useState } from "react";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import {
  apiError, canConfirm, embedUrl, fileUrl, formatDuration, materialHint, secondsUntilConfirm, type Material,
} from "@/lib/training";

const HEARTBEAT_MS = 10_000;

interface YTPlayer { getCurrentTime(): number; getDuration(): number; getPlayerState(): number; destroy(): void }
interface YTNamespace {
  Player: new (el: HTMLElement, opts: Record<string, unknown>) => YTPlayer;
  PlayerState: { PLAYING: number; ENDED: number; PAUSED: number };
}
declare global {
  interface Window { YT?: YTNamespace; onYouTubeIframeAPIReady?: () => void }
}

let ytLoading: Promise<YTNamespace> | null = null;
function loadYouTubeApi(): Promise<YTNamespace> {
  if (window.YT?.Player) return Promise.resolve(window.YT);
  if (!ytLoading) {
    ytLoading = new Promise((resolve, reject) => {
      const prev = window.onYouTubeIframeAPIReady;
      window.onYouTubeIframeAPIReady = () => { prev?.(); if (window.YT) resolve(window.YT); };
      const s = document.createElement("script");
      s.src = "https://www.youtube.com/iframe_api";
      s.async = true;
      s.onerror = () => { ytLoading = null; reject(new Error("YouTube player could not load")); };
      document.head.appendChild(s);
    });
  }
  return ytLoading;
}

export default function MaterialViewer({ assignmentId, material: m, disabled, onProgress }: {
  assignmentId: string; material: Material; disabled: boolean; onProgress: () => void;
}) {
  const { showToast } = useToast();
  const [busy, setBusy] = useState(false);
  const [local, setLocal] = useState<Material>(m);
  const [, tick] = useState(0);

  const post = useCallback(async (action: "open" | "progress" | "confirm", body: Record<string, unknown> = {}) => {
    if (disabled) return null;
    const res = await clientApi.post<{ data: { material: Material } }>(
      API.training.myMaterial(assignmentId, m.id, action), body);
    const next = res.data.data.material;
    const wasDone = !!local.progress?.completed_at;
    setLocal(next);
    if (!wasDone && next.progress?.completed_at) onProgress();
    return next;
  }, [assignmentId, m.id, disabled, local.progress?.completed_at, onProgress]);

  // Record "opened" once the material is shown (never completes it).
  useEffect(() => {
    if (!m.progress?.opened_at) post("open").catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [m.id]);

  // Countdown for the document minimum reading time.
  useEffect(() => {
    if (m.material_type !== "document" || local.progress?.completed_at) return;
    const t = setInterval(() => tick(n => n + 1), 1000);
    return () => clearInterval(t);
  }, [m.material_type, local.progress?.completed_at]);

  async function confirm() {
    setBusy(true);
    try {
      await post("confirm");
      showToast("Marked as complete.", "success");
    } catch (e) {
      showToast(apiError(e, "Could not save."), "error");
    } finally {
      setBusy(false);
    }
  }

  const wait = secondsUntilConfirm(local);
  const done = !!local.progress?.completed_at;

  return (
    <div className="card card-body" data-testid="material-viewer">
      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, marginBottom: 10, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: 15 }}>{m.title}</div>
          {m.description && <div className="text-[12px] text-[var(--on-variant)] mt-1">{m.description}</div>}
        </div>
        <span className={`badge ${done ? "badge-success" : "badge-info"}`}>{materialHint(local)}</span>
      </div>

      {m.material_type === "video" && <UploadedVideo material={m} onBeat={(p, d) => post("progress", { position: p, duration: d })} />}
      {m.material_type === "external_video" && m.provider === "direct" && (
        <TrackedVideo src={m.external_url} onBeat={(p, d) => post("progress", { position: p, duration: d })} />
      )}
      {m.material_type === "external_video" && m.provider === "youtube" && (
        <YouTubeVideo material={m} onBeat={(p, d) => post("progress", { position: p, duration: d })} />
      )}
      {m.material_type === "external_video" && m.provider === "vimeo" && (
        <div style={{ position: "relative", paddingTop: "56.25%" }}>
          <iframe src={embedUrl(m)} title={m.title} allow="fullscreen; picture-in-picture" allowFullScreen
                  referrerPolicy="strict-origin-when-cross-origin" sandbox="allow-scripts allow-same-origin allow-presentation"
                  style={{ position: "absolute", inset: 0, width: "100%", height: "100%", border: 0, borderRadius: 8 }} />
        </div>
      )}
      {m.material_type === "external_video" && (
        <div className="text-[12px] mt-2">
          Video not playing?{" "}
          <a href={m.external_url} target="_blank" rel="noopener noreferrer" className="text-[var(--primary)]">
            Open the original <i className="ti ti-external-link" />
          </a>
        </div>
      )}

      {m.material_type === "document" && (m.file_format === "pdf" ? (
        <PdfFrame materialId={m.id} title={m.title} />
      ) : (
        <div className="text-[13px] py-4">
          {m.file_format.toUpperCase()} files open in PowerPoint / Word.{" "}
          <a href={fileUrl(m.id)} download className="btn btn-ghost" style={{ marginLeft: 8 }}>
            <i className="ti ti-download" /> Download
          </a>
        </div>
      ))}

      {!done && canConfirm(local) && !disabled && (
        <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 10, marginTop: 12 }}>
          {wait > 0 && <span className="text-[12px] text-[var(--on-variant)]">Available in {formatDuration(wait)}</span>}
          <button className="btn btn-filled" onClick={confirm} disabled={busy || wait > 0}>
            {m.material_type === "document" ? "I have read this" : "I have watched this"}
          </button>
        </div>
      )}
    </div>
  );
}

// The app sends X-Frame-Options: DENY, so a PDF is fetched (access-checked,
// same origin) and shown from a local blob: URL — as DocPreviewModal does.
export function PdfFrame({ materialId, title }: { materialId: string; title: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let created: string | null = null;
    let alive = true;
    clientApi.get(API.training.materialFile(materialId), { responseType: "blob", timeout: 60000 })
      .then(r => {
        if (!alive) return;
        created = URL.createObjectURL(new Blob([r.data as Blob], { type: "application/pdf" }));
        setUrl(created);
      })
      .catch(() => { if (alive) setFailed(true); });
    return () => { alive = false; if (created) URL.revokeObjectURL(created); };
  }, [materialId]);
  if (failed) {
    return (
      <div className="alert alert-error">
        The document could not be shown. <a href={fileUrl(materialId)} download>Download it</a> instead.
      </div>
    );
  }
  if (!url) return <div className="text-[13px] text-[var(--on-variant)] py-6">Loading document…</div>;
  return (
    <iframe src={url} title={title}
            style={{ width: "100%", height: "70vh", border: "1px solid var(--outline-v)", borderRadius: 8 }} />
  );
}

// Returns a callback that never changes identity. The latest onBeat is kept in
// a ref: if `beat` changed with every progress response, the YouTube player
// (created in an effect that depends on it) would be destroyed and rebuilt —
// stopping playback each time progress was saved.
function useHeartbeat(onBeat: (position: number, duration: number | null) => Promise<unknown>) {
  const last = useRef(0);
  const latest = useRef(onBeat);
  useEffect(() => { latest.current = onBeat; }, [onBeat]);
  return useCallback((position: number, duration: number | null, force = false) => {
    const now = Date.now();
    if (!force && now - last.current < HEARTBEAT_MS) return;
    last.current = now;
    latest.current(position, duration && Number.isFinite(duration) ? duration : null).catch(() => undefined);
  }, []);
}

function TrackedVideo({ src, onBeat }: { src: string; onBeat: (p: number, d: number | null) => Promise<unknown> }) {
  const beat = useHeartbeat(onBeat);
  const [failed, setFailed] = useState(false);
  if (failed) return <div className="alert alert-error">This video could not be played.</div>;
  return (
    <video src={src} controls controlsList="nodownload" preload="metadata" playsInline
           style={{ width: "100%", maxHeight: "70vh", borderRadius: 8, background: "#000" }}
           onPlay={e => beat(e.currentTarget.currentTime, e.currentTarget.duration, true)}
           onTimeUpdate={e => beat(e.currentTarget.currentTime, e.currentTarget.duration)}
           onPause={e => beat(e.currentTarget.currentTime, e.currentTarget.duration, true)}
           onEnded={e => beat(e.currentTarget.currentTime, e.currentTarget.duration, true)}
           onError={() => setFailed(true)}
           onContextMenu={e => e.preventDefault()} />
  );
}

function UploadedVideo({ material, onBeat }: { material: Material; onBeat: (p: number, d: number | null) => Promise<unknown> }) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    clientApi.get<{ data: { url: string | null } }>(API.training.videoSource(material.id))
      .then(r => { if (alive) setSrc(r.data.data.url || fileUrl(material.id)); })
      .catch(() => { if (alive) setSrc(fileUrl(material.id)); });
    return () => { alive = false; };
  }, [material.id]);
  if (!src) return <div className="text-[13px] text-[var(--on-variant)] py-6">Loading video…</div>;
  return <TrackedVideo src={src} onBeat={onBeat} />;
}

function YouTubeVideo({ material, onBeat }: { material: Material; onBeat: (p: number, d: number | null) => Promise<unknown> }) {
  const holder = useRef<HTMLDivElement>(null);
  const beat = useHeartbeat(onBeat);
  const [failed, setFailed] = useState("");

  useEffect(() => {
    let player: YTPlayer | null = null;
    let timer: ReturnType<typeof setInterval> | null = null;
    let alive = true;
    loadYouTubeApi().then(YT => {
      if (!alive || !holder.current) return;
      const el = document.createElement("div");
      holder.current.appendChild(el);
      player = new YT.Player(el, {
        host: "https://www.youtube-nocookie.com",
        videoId: material.embed_id,
        width: "100%", height: "100%",
        playerVars: { rel: 0, modestbranding: 1, playsinline: 1 },
        events: {
          onStateChange: (ev: { data: number }) => {
            if (!player) return;
            if (ev.data === YT.PlayerState.PLAYING) {
              beat(player.getCurrentTime(), player.getDuration(), true);
              if (!timer) timer = setInterval(() => player && beat(player.getCurrentTime(), player.getDuration()), 2000);
            } else {
              if (timer) { clearInterval(timer); timer = null; }
              if (ev.data === YT.PlayerState.PAUSED || ev.data === YT.PlayerState.ENDED)
                beat(player.getCurrentTime(), player.getDuration(), true);
            }
          },
          onError: () => setFailed("This video can't be played here (it may not allow embedding)."),
        },
      });
    }).catch(() => setFailed("The YouTube player could not load."));
    return () => {
      alive = false;
      if (timer) clearInterval(timer);
      player?.destroy();
    };
  }, [material.embed_id, beat]);

  if (failed) return <div className="alert alert-error">{failed}</div>;
  return (
    <div style={{ position: "relative", paddingTop: "56.25%" }}>
      <div ref={holder} style={{ position: "absolute", inset: 0 }} className="yt-holder" />
    </div>
  );
}
