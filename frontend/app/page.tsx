"use client";

import Link from "next/link";
import { ChangeEvent, DragEvent, useEffect, useRef, useState } from "react";
import {
  AnalysisResponse, CandidateSession, PortraitJob, PortraitOptions, PortraitStyle, RenderResult, RuntimeStatus,
  analyzePhoto, createPortraitJob, getCandidateSession, getPortraitJob, getRuntime, getStyles,
  refineCandidate, renderCandidate, selectCandidate, submitFeedback,
} from "@/lib/api";

const STORAGE_KEY = "portrait-studio-workflow-v1";
const TERMINAL = new Set(["failed", "cancelled", "completed", "awaiting_selection", "rendering"]);
const DEFAULT_OPTIONS: PortraitOptions = { crop: "original", background: "keep", output_type: "social", candidate_count: 4 };
const LABELS: Record<string, string> = {
  original: "Keep photo framing", face: "Face portrait", half_body: "Upper body", full_body: "Full photo",
  keep: "Keep background", blur: "Soft blur", replace: "New studio setting", transparent: "Transparent", surprise: "Let the style decide",
  social: "Social profile", canvas: "Canvas print", frame: "Wall frame", gift: "Gift", sticker: "Sticker",
};
const REFINEMENTS = [
  { id: "lighting", label: "Softer light", instruction: "Soften the lighting and reduce harsh shadows, preserving the face." },
  { id: "color", label: "Warmer colors", instruction: "Gently warm the overall color palette while preserving the natural skin tone." },
  { id: "background", label: "Simpler background", instruction: "Simplify the background to a quiet neutral setting, keeping the subject unchanged." },
  { id: "cleanup", label: "Clean up details", instruction: "Clean up small stray marks in the background without changing the face or body." },
];
const STAGES: Record<string, string> = {
  generation_queued: "Waiting for the image engine", refinement_queued: "Waiting to refine your portrait",
  queued: "Waiting for the image engine", running: "Creating portraits", processing: "Processing portraits",
  checking_likeness: "Checking likeness against your original photo", candidates_ready: "Portraits ready to choose",
  generation_retry_scheduled: "Reconnecting to the image engine", candidate_selected: "Portrait selected", render_completed: "Export ready",
};
const errorMessage = (error: unknown) => error instanceof Error ? error.message : "Something went wrong. Please try again.";

export default function HomePage() {
  const input = useRef<HTMLInputElement>(null);
  const epoch = useRef(0);
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [styles, setStyles] = useState<PortraitStyle[]>([]);
  const [styleId, setStyleId] = useState("");
  const [options, setOptions] = useState(DEFAULT_OPTIONS);
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null);
  const [runtimeError, setRuntimeError] = useState("");
  const [checkingRuntime, setCheckingRuntime] = useState(false);
  const [job, setJob] = useState<PortraitJob | null>(null);
  const [session, setSession] = useState<CandidateSession | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [render, setRender] = useState<RenderResult | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [restored, setRestored] = useState(false);
  const [format, setFormat] = useState("png");
  const [size, setSize] = useState(0);
  const [refinement, setRefinement] = useState("lighting");
  const [rating, setRating] = useState<number | null>(null);
  const [feedback, setFeedback] = useState("");
  const [feedbackSaved, setFeedbackSaved] = useState(false);

  const generating = Boolean(job && !TERMINAL.has(job.status));
  const locked = Boolean(busy) || generating;
  const style = styles.find((item) => item.id === styleId);
  const confirmed = Boolean(selected && session?.selected_candidate_id === selected);
  const acceptedPhoto = analysis && analysis.next_step !== "request_better_photo";

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  async function checkRuntime() {
    setCheckingRuntime(true); setRuntimeError("");
    try { setRuntime(await getRuntime()); }
    catch (err) { setRuntime(null); setRuntimeError(errorMessage(err)); }
    finally { setCheckingRuntime(false); }
  }

  useEffect(() => {
    let disposed = false;
    getStyles().then((items) => { if (!disposed) setStyles(items); }).catch((err) => { if (!disposed) setError(errorMessage(err)); });
    void checkRuntime();
    async function restore() {
      try {
        const raw = window.sessionStorage.getItem(STORAGE_KEY);
        if (!raw) return;
        const saved = JSON.parse(raw) as { jobId?: string; sessionId?: string; styleId?: string; options?: PortraitOptions };
        if (saved.styleId) setStyleId(saved.styleId);
        if (saved.options) setOptions(saved.options);
        if (saved.sessionId) {
          const previous = await getCandidateSession(saved.sessionId);
          if (disposed) return;
          setSession(previous); setSelected(previous.selected_candidate_id);
        }
        if (saved.jobId) {
          const previous = await getPortraitJob(saved.jobId);
          if (!disposed) setJob(previous);
        }
        if (!disposed) setNotice("Your current portrait session has been restored.");
      } catch (err) {
        if (!disposed) setNotice(errorMessage(err));
        try { window.sessionStorage.removeItem(STORAGE_KEY); } catch { /* Private browsing can disable storage. */ }
      } finally { if (!disposed) setRestored(true); }
    }
    void restore();
    return () => { disposed = true; };
  }, []);

  useEffect(() => {
    if (!restored) return;
    try {
      if (job || session) window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ jobId: job?.id, sessionId: session?.id, styleId, options }));
      else window.sessionStorage.removeItem(STORAGE_KEY);
    } catch { /* The workflow still works when browser storage is unavailable. */ }
  }, [job, session, styleId, options, restored]);

  const jobId = job?.id;
  useEffect(() => {
    if (!jobId) return;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    let failures = 0;
    async function poll() {
      try {
        const current = await getPortraitJob(jobId!);
        if (disposed) return;
        setJob(current);
        if (current.candidate_session_id) {
          const candidates = await getCandidateSession(current.candidate_session_id);
          if (disposed) return;
          setSession(candidates); setSelected(candidates.selected_candidate_id); setRender(null);
          setError(""); return;
        }
        if (current.status === "failed" || current.status === "cancelled") {
          setError(current.error?.message ?? "No portraits passed the checks. Try another photo or style."); return;
        }
        if (current.status === "completed") return;
        failures = 0;
      } catch (err) {
        if (disposed) return;
        setError(errorMessage(err));
        failures += 1;
        if (failures >= 5) { setJob((previous) => previous ? { ...previous, status: "failed" } : null); return; }
      }
      if (!disposed) timer = setTimeout(poll, 2000);
    }
    void poll();
    return () => { disposed = true; clearTimeout(timer); };
  }, [jobId]);

  function resetResults() {
    setJob(null); setSession(null); setSelected(null); setRender(null); setError("");
    setRating(null); setFeedback(""); setFeedbackSaved(false); setNotice("");
  }

  function chooseFile(next: File) {
    if (locked) return;
    epoch.current += 1;
    resetResults(); setAnalysis(null); setFile(null); setPreview(null); setStyleId("");
    if (!["image/jpeg", "image/png", "image/webp"].includes(next.type)) { setError("Choose a JPG, PNG, or WebP photo."); return; }
    if (!next.size || next.size > 20 * 1024 * 1024) { setError("Choose a nonempty photo smaller than 20 MB."); return; }
    setFile(next); setPreview(URL.createObjectURL(next));
  }
  function onInput(event: ChangeEvent<HTMLInputElement>) { const next = event.target.files?.[0]; if (next) chooseFile(next); event.target.value = ""; }
  function onDrop(event: DragEvent<HTMLDivElement>) { event.preventDefault(); setDragging(false); const next = event.dataTransfer.files[0]; if (next) chooseFile(next); }
  function chooseStyle(next: PortraitStyle) {
    if (locked) return;
    resetResults(); setStyleId(next.id);
    const backgrounds = next.background_modes.filter((item) => runtime?.background_removal || !["blur", "transparent"].includes(item));
    setOptions((old) => ({ ...old, background: backgrounds.includes(old.background) ? old.background : backgrounds[0], output_type: next.output_types.includes(old.output_type) ? old.output_type : next.output_types[0] }));
  }
  async function analyze() {
    if (!file) return;
    const current = epoch.current;
    resetResults(); setBusy("analyze");
    try {
      const result = await analyzePhoto(file);
      if (epoch.current !== current) return;
      setAnalysis(result);
      if (result.next_step !== "request_better_photo" && styles[0]) chooseStyle(styles[0]);
    } catch (err) { if (epoch.current === current) setError(errorMessage(err)); }
    finally { if (epoch.current === current) setBusy(""); }
  }
  async function generate() {
    if (!file || !styleId || !acceptedPhoto) return;
    resetResults(); setBusy("generate");
    try { setJob(await createPortraitJob(file, styleId, options)); }
    catch (err) { setError(errorMessage(err)); }
    finally { setBusy(""); }
  }
  async function confirm() {
    if (!session || !selected) return;
    setBusy("select"); setError("");
    try { setSession(await selectCandidate(session.id, selected)); setFeedbackSaved(false); }
    catch (err) { setError(errorMessage(err)); }
    finally { setBusy(""); }
  }
  async function refine() {
    if (!session || !confirmed) return;
    const choice = REFINEMENTS.find((item) => item.id === refinement)!;
    setBusy("refine"); setError(""); setRender(null);
    try { setJob(await refineCandidate(session.id, styleId, choice.id, choice.instruction, options)); }
    catch (err) { setError(errorMessage(err)); }
    finally { setBusy(""); }
  }
  async function exportPortrait() {
    if (!session || !confirmed) return;
    setBusy("export"); setError("");
    try { setRender(await renderCandidate(session.id, { output_format: format, max_dimension: size || null })); }
    catch (err) { setError(errorMessage(err)); }
    finally { setBusy(""); }
  }
  async function saveFeedback(accepted: boolean) {
    if (!session || !selected || !rating) return;
    setBusy("feedback"); setError("");
    try { await submitFeedback(session.id, selected, rating, accepted, feedback); setFeedbackSaved(true); }
    catch (err) { setError(errorMessage(err)); }
    finally { setBusy(""); }
  }
  function download() {
    if (!render) return;
    const bytes = Uint8Array.from(atob(render.image_base64), (char) => char.charCodeAt(0));
    const url = URL.createObjectURL(new Blob([bytes], { type: render.content_type }));
    const link = document.createElement("a"); link.href = url; link.download = render.filename;
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  }

  return <main className="page"><div className="shell">
    <header className="header"><Link href="/" className="brand">Portrait Studio AI</Link><span className="badge">Made for your face</span></header>
    <section className="hero">
      <div><div className="eyebrow">One photo. Your own style.</div><h1>Art that still<br />looks like you.</h1>
        <p className="lede">Choose a portrait style, compare the results, and make it yours. Each portrait is checked against your original photo before you see it.</p>
        <div className="promise"><span>Local processing</span><span>Likeness checks</span><span>Your final choice</span></div>
      </div>
      <div className="card upload">
        <div className={`dropzone ${dragging ? "active" : ""} ${preview ? "hasImage" : ""}`} onDragOver={(e) => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={onDrop}>
          {preview ? <><img className="preview" src={preview} alt="Your original portrait" /><div className="overlay"><strong>{file?.name}</strong></div></>
            : <div><div className="uploadIcon" aria-hidden="true">↑</div><strong>Start with one clear portrait</strong><p className="fineprint">One person · JPG, PNG, or WebP · Up to 20 MB</p><div className="actions"><button className="primary" disabled={locked} onClick={() => input.current?.click()}>Choose photo</button></div></div>}
        </div>
        <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={onInput} aria-label="Upload portrait" />
        {preview && <div className="actions"><button className="secondary" disabled={locked} onClick={() => input.current?.click()}>Replace photo</button><button className="primary" disabled={locked} onClick={analyze}>{busy === "analyze" ? "Checking photo…" : "Analyze photo"}</button></div>}
        {analysis && <div className={`status ${acceptedPhoto ? "success" : "error"}`} role="status"><strong>{acceptedPhoto ? "Your photo is ready" : "Please try a clearer photo"}</strong><p>{analysis.identity.guidance.join(" ")}</p><span>{analysis.analysis.width} × {analysis.analysis.height} · {analysis.identity.face_count} face{analysis.identity.face_count === 1 ? "" : "s"}</span>{analysis.next_step === "enhance" && <p>We’ll gently improve the lighting and clarity before generating.</p>}</div>}
      </div>
    </section>

    <aside className="runtimeBar" aria-label="Image engine status"><div><strong>{checkingRuntime ? "Checking your image engine…" : runtime?.ready ? "Image engine ready" : "Local model setup needed"}</strong><p className="fineprint">{runtimeError || (runtime?.ready ? "Ready to create portraits on this computer." : "Photo analysis works now. Connect the local models to generate portraits.")}</p></div><button className="secondary" disabled={checkingRuntime} onClick={checkRuntime}>Check connection</button>
      {!runtime?.ready && <details><summary>Show setup details</summary><ul>{runtime?.checks.map((item) => <li key={item.id}>{item.ready ? "✓ " : "• "}{item.message}</li>)}</ul><a href="https://github.com/samuel054/Portrait-Studio-AI1/blob/codex/finish-portrait-studio-mvp/docs/LOCAL_SETUP.md" target="_blank" rel="noreferrer">Open local setup guide</a></details>}
    </aside>
    {notice && <p className="status" role="status">{notice}</p>}
    {error && <div className="status error" role="alert">{error}{job?.status === "failed" && file && <div className="actions"><button className="secondary" onClick={generate} disabled={locked || !runtime?.ready}>Try generation again</button></div>}</div>}

    {(acceptedPhoto || session || job) && <section className="styleSection" aria-labelledby="styles-title"><div className="sectionHeading"><div><div className="eyebrow">01 / Make it yours</div><h2 id="styles-title">Choose a style</h2></div><p>Likeness checking stays on for every style.</p></div>
      <div className="styleGrid">{styles.map((item) => <button type="button" key={item.id} disabled={locked || !file} className={`styleCard ${styleId === item.id ? "selected" : ""}`} aria-pressed={styleId === item.id} onClick={() => chooseStyle(item)}><div className={`styleSwatch ${item.category}`} aria-hidden="true"><span>{item.category === "painting" ? "◌" : item.category === "chibi" ? "✦" : "◈"}</span></div><span className="styleCategory">{item.category}</span><strong>{item.name}</strong><span>{item.description}</span></button>)}</div>
      {style && <div className="optionsPanel card"><fieldset disabled={locked || Boolean(session)}><legend>Framing</legend><div className="choices">{["original", "face", "half_body"].map((id) => <button type="button" key={id} className={options.crop === id ? "primary" : "secondary"} aria-pressed={options.crop === id} onClick={() => setOptions({ ...options, crop: id })}>{LABELS[id]}</button>)}</div></fieldset>
        <fieldset disabled={locked || Boolean(session)}><legend>Background</legend><div className="choices">{style.background_modes.map((id) => <button type="button" key={id} disabled={["blur", "transparent"].includes(id) && !runtime?.background_removal} title={["blur", "transparent"].includes(id) && !runtime?.background_removal ? "Requires the optional local background model" : undefined} className={options.background === id ? "primary" : "secondary"} aria-pressed={options.background === id} onClick={() => setOptions({ ...options, background: id })}>{LABELS[id]}</button>)}</div></fieldset>
        <fieldset disabled={locked || Boolean(session)}><legend>Where will you use it?</legend><div className="choices">{style.output_types.map((id) => <button type="button" key={id} className={options.output_type === id ? "primary" : "secondary"} aria-pressed={options.output_type === id} onClick={() => setOptions({ ...options, output_type: id })}>{LABELS[id]}</button>)}</div></fieldset>
        <fieldset disabled={locked || Boolean(session)}><legend>How many options?</legend><div className="choices">{[2, 3, 4].map((count) => <button type="button" key={count} className={options.candidate_count === count ? "primary" : "secondary"} aria-pressed={options.candidate_count === count} onClick={() => setOptions({ ...options, candidate_count: count })}>{count} portraits</button>)}</div></fieldset>
        {!session && <div className="styleActions"><span>Ready for <strong>{style.name}</strong></span><button className="primary" disabled={locked || !runtime?.ready || !file} onClick={generate}>{busy === "generate" ? "Preparing your photo…" : "Generate portraits"}</button></div>}
      </div>}
    </section>}

    {generating && <section className="styleSection progressPanel" aria-live="polite"><div className="eyebrow">02 / Creating your portraits</div><h2>{STAGES[job!.stage] ?? "Working on your portraits"}</h2><div className="indeterminate" aria-hidden="true" /><p className="fineprint">The time depends on your computer. You can refresh this page and return to this session.</p></section>}

    {session && <section className="styleSection" aria-labelledby="candidates-title"><div className="eyebrow">03 / You choose</div><h2 id="candidates-title">Which portrait feels like you?</h2><p className="lede small">{session.candidates.length} portrait{session.candidates.length === 1 ? "" : "s"} passed the checks. Compare the face and details before choosing.</p>
      <div className="candidateGrid">{session.candidates.map((candidate) => <button key={candidate.id} type="button" disabled={locked} className={`styleCard candidate ${selected === candidate.id ? "selected" : ""}`} aria-pressed={selected === candidate.id} onClick={() => { setSelected(candidate.id); setRender(null); setFeedbackSaved(false); }}><img src={`data:${candidate.content_type};base64,${candidate.image_base64}`} alt={`Portrait option ${candidate.id}`} /><strong>Option {candidate.id}{candidate.recommended ? " · Recommended" : ""}</strong><span>Quality and likeness: {candidate.score.toFixed(0)}/100</span></button>)}</div>
      <div className="styleActions"><span>{selected ? `Your choice: ${selected}` : "Choose a portrait to continue."}</span><button className="primary" onClick={confirm} disabled={locked || !selected || confirmed}>{busy === "select" ? "Saving choice…" : confirmed ? `Option ${selected} confirmed` : "Confirm selection"}</button></div>
      {confirmed && <div className="finishGrid">
        <div className="card optionsPanel"><div className="eyebrow">Optional</div><h3>A finishing touch</h3><p className="fineprint">Refined options are checked against your original photo again.</p><div className="choices">{REFINEMENTS.map((item) => <button key={item.id} disabled={locked} aria-pressed={refinement === item.id} className={refinement === item.id ? "primary" : "secondary"} onClick={() => setRefinement(item.id)}>{item.label}</button>)}</div><button className="secondary wide" disabled={locked || !runtime?.ready} onClick={refine}>{busy === "refine" || generating ? "Refining…" : "Create refined options"}</button></div>
        <div className="card optionsPanel"><div className="eyebrow">04 / Take it with you</div><h3>Export your portrait</h3><fieldset disabled={locked}><legend>File format</legend><div className="choices">{["png", "jpeg", "webp"].map((item) => <button key={item} aria-pressed={format === item} className={format === item ? "primary" : "secondary"} onClick={() => { setFormat(item); setRender(null); }}>{item.toUpperCase()}</button>)}</div></fieldset><label htmlFor="export-size">Image size</label><select id="export-size" value={size} disabled={locked} onChange={(event) => { setSize(Number(event.target.value)); setRender(null); }}><option value={0}>Original resolution</option><option value={1024}>Fit within 1024 px</option><option value={2048}>Fit within 2048 px</option></select><p className="fineprint">Keeps proportions. Smaller originals are not enlarged.{format === "jpeg" ? " Transparency becomes white in JPEG." : ""}</p><button className="primary wide" disabled={locked} onClick={exportPortrait}>{busy === "export" ? "Preparing file…" : "Prepare download"}</button>{render && <div className="status success" role="status"><strong>{render.width} × {render.height} · {render.content_type.replace("image/", "").toUpperCase()}</strong><button className="primary wide" onClick={download}>Download portrait</button></div>}</div>
      </div>}
      {confirmed && <details className="feedbackPanel"><summary>Help improve the results (optional)</summary><div className="choices" role="group" aria-label="Rate your portrait">{[1, 2, 3, 4, 5].map((value) => <button key={value} disabled={locked} className={rating === value ? "primary" : "secondary"} aria-pressed={rating === value} onClick={() => { setRating(value); setFeedbackSaved(false); }}>{value} ★</button>)}</div><label htmlFor="feedback">Your comments</label><textarea id="feedback" value={feedback} maxLength={1000} onChange={(event) => { setFeedback(event.target.value); setFeedbackSaved(false); }} /><div className="choices"><button className="secondary" disabled={locked || !rating || feedbackSaved} onClick={() => saveFeedback(true)}>I like this result</button><button className="secondary" disabled={locked || !rating || feedbackSaved} onClick={() => saveFeedback(false)}>Needs improvement</button></div>{feedbackSaved && <p role="status">Thank you. Your feedback was saved.</p>}</details>}
    </section>}
    <footer className="footer"><p>Portraits stay in this local session for up to 60 minutes. Download the ones you want to keep.</p><p>No portrait or face data is included in feedback.</p></footer>
  </div></main>;
}
