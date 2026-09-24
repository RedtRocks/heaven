"use client";

import dynamic from "next/dynamic";
import { forwardRef } from "react";
import type { FaceStageHandle } from "./FaceStageCanvas";

// TalkingHead touches WebGL/AudioContext/window at import time, so it can only
// ever run in the browser. Loading it via next/dynamic with ssr:false keeps it
// out of the server bundle and out of the initial client bundle too.
const FaceStageCanvas = dynamic(() => import("./FaceStageCanvas"), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-64 sm:h-80 bg-gradient-to-br from-slate-100 to-slate-200 dark:from-slate-800 dark:to-slate-700 rounded-lg border border-slate-300 dark:border-slate-600">
      <p className="text-slate-500 dark:text-slate-400 text-sm">Loading 3D face…</p>
    </div>
  ),
});

/**
 * The Owner's real-time 3D talking face. Renders `/avatar/owner.glb` (gitignored
 * Likeness) via met4citizen/TalkingHead. Call `speak(text)` on the ref whenever
 * the Clone replies, so the face can be driven from outside (see ClonePage).
 */
const FaceStage = forwardRef<FaceStageHandle>(function FaceStage(_props, ref) {
  return <FaceStageCanvas ref={ref} />;
});

export default FaceStage;
