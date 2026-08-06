"use client";

import { ChangeEvent, DragEvent, useEffect, useRef, useState } from "react";
import {
  AnalysisResponse,
  PortraitStyle,
  analyzePhoto,
  getStyles,
} from "@/lib/api";

const ALLOWED = ["image/jpeg", "image/png", "image/webp"];
const MAX_SIZE = 20 * 1024 * 1024;

export default function HomePage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [styles, setStyles] = useState<PortraitStyle[]>([]);
  const [selectedStyle, setSelectedStyle] = useState<string | null>(null);
  const [stylesError, setStylesError] = useState("");
  const [status, setStatus] = useState<"idle" | "analyzing" | "done" | "error">("idle");
  const [message, setMessage] = useState("");

  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview);
    };
  }, [preview]);

  useEffect(() => {
    if (!analysis || analysis.next_step === "request_better_photo") return;
    getStyles()
      .then((items) => {
        setStyles(items);
        setSelectedStyle((current) => current ?? items[0]?.id ?? null);
      })
      .catch((error: unknown) => {
        setStylesError(error instanceof Error ? error.message : "Style catalog unavailable.");
      });
  }, [analysis]);

  function chooseFile(next: File) {
    setAnalysis(null);
    setStyles([]);
    setSelectedStyle(null);
    setStylesError("");
    setMessage("");
    setStatus("idle");

    if (!ALLOWED.includes(next.type)) {
      setStatus("error");
      setMessage("Upload a JPG, PNG, or WEBP image.");
      return;
    }
    if (next.size > MAX_SIZE) {
      setStatus("error");
      setMessage("The photo must be smaller than 20 MB.");
      return;
    }

    if (preview) URL.revokeObjectURL(preview);
    setFile(next);
    setPreview(URL.createObjectURL(next));
  }

  function onInput(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0];
    if (selected) chooseFile(selected);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    const selected = event.dataTransfer.files?.[0];
    if (selected) chooseFile(selected);
  }

  async function runAnalysis() {
    if (!file) return;
    setStatus("analyzing");
    setMessage("Checking face visibility, sharpness, lighting, and identity readiness…");
    try {
      const result = await analyzePhoto(file);
      setAnalysis(result);
      setStatus("done");
      setMessage(
        result.next_step === "request_better_photo"
          ? "This photo needs a clearer face before generation."
          : result.next_step === "enhance"
            ? "Photo accepted. We will enhance it before generation."
            : "Photo accepted and ready for style selection.",
      );
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Analysis failed.");
    }
  }

  const canChooseStyle = analysis && analysis.next_step !== "request_better_photo";

  return (
    <main className="page">
      <div className="shell">
        <header className="header">
          <div className="brand">Portrait Studio AI</div>
          <div className="badge">Identity-first · Open source</div>
        </header>

        <section className="hero">
          <div>
            <div className="eyebrow">Your face stays your face</div>
            <h1>Turn one photo into art that still looks like you.</h1>
            <p className="lede">
              Upload a portrait and we will check image quality and identity readiness before any
              generation begins. No blind face replacement. No generic stranger wearing your clothes.
            </p>
            <div className="promise">
              <span>Automatic quality check</span>
              <span>Identity-safe ranking</span>
              <span>You choose A, B, C, or D</span>
            </div>
          </div>

          <div className="card upload">
            <div
              className={`dropzone ${dragging ? "active" : ""} ${preview ? "hasImage" : ""}`}
              onDragEnter={(event) => {
                event.preventDefault();
                setDragging(true);
              }}
              onDragOver={(event) => event.preventDefault()}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
            >
              {preview ? (
                <>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img className="preview" src={preview} alt="Selected portrait preview" />
                  <div className="overlay">
                    <strong>{file?.name}</strong>
                    <div className="fineprint">
                      {file ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : ""}
                    </div>
                  </div>
                </>
              ) : (
                <div>
                  <div className="uploadIcon">↑</div>
                  <strong>Drop your portrait here</strong>
                  <p className="fineprint">JPG, PNG, or WEBP · Maximum 20 MB</p>
                  <div className="actions">
                    <button className="primary" onClick={() => inputRef.current?.click()}>
                      Choose photo
                    </button>
                  </div>
                </div>
              )}
            </div>

            <input
              ref={inputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              hidden
              onChange={onInput}
            />

            {preview && (
              <div className="actions">
                <button className="secondary" onClick={() => inputRef.current?.click()}>
                  Replace photo
                </button>
                <button className="primary" onClick={runAnalysis} disabled={status === "analyzing"}>
                  {status === "analyzing" ? "Analyzing…" : "Analyze photo"}
                </button>
              </div>
            )}

            {status !== "idle" && (
              <div className={`status ${status === "error" ? "error" : status === "done" ? "success" : ""}`}>
                {message}
                {analysis && (
                  <div className="fineprint">
                    {analysis.identity.face_count} face detected · {analysis.analysis.megapixels.toFixed(1)} MP ·
                    identity {analysis.identity.identity_readiness}
                  </div>
                )}
              </div>
            )}
          </div>
        </section>

        {canChooseStyle && (
          <section className="styleSection" aria-labelledby="style-title">
            <div className="sectionHeading">
              <div>
                <div className="eyebrow">Step 2</div>
                <h2 id="style-title">Choose your portrait style</h2>
              </div>
              <p>Every option keeps identity preservation active.</p>
            </div>

            {stylesError ? (
              <div className="status error">{stylesError}</div>
            ) : styles.length === 0 ? (
              <div className="status">Loading styles…</div>
            ) : (
              <div className="styleGrid">
                {styles.map((style) => (
                  <button
                    key={style.id}
                    type="button"
                    className={`styleCard ${selectedStyle === style.id ? "selected" : ""}`}
                    onClick={() => setSelectedStyle(style.id)}
                    aria-pressed={selectedStyle === style.id}
                  >
                    <span className="styleCategory">{style.category}</span>
                    <strong>{style.name}</strong>
                    <span>{style.description}</span>
                    <small>
                      Identity {style.identity_priority.replace("_", " ")} · pose preserved · clothing preserved
                    </small>
                  </button>
                ))}
              </div>
            )}

            {selectedStyle && (
              <div className="styleActions">
                <span>
                  Selected: <strong>{styles.find((style) => style.id === selectedStyle)?.name}</strong>
                </span>
                <button className="primary" type="button">
                  Continue to generation
                </button>
              </div>
            )}
          </section>
        )}

        <section className="steps" aria-label="How it works">
          <article className="card step">
            <strong>1. We inspect first</strong>
            <p>Blur, lighting, resolution, visible faces, and identity risk are checked before generation.</p>
          </article>
          <article className="card step">
            <strong>2. We generate safely</strong>
            <p>Open-source models create several candidates while identity rules stay active.</p>
          </article>
          <article className="card step">
            <strong>3. You make the call</strong>
            <p>Only safe candidates are shown. Pick A, B, C, or D, then refine and export.</p>
          </article>
        </section>
      </div>
    </main>
  );
}
