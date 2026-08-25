import { spawn } from "node:child_process";
import { mkdtemp, rm, writeFile, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

/**
 * FFmpeg renderer for a THRAANSH render spec.
 *
 * Contract with the app (see src/lib/core/render.server.ts):
 *  - spec.narration.audio_url is the ONE narration track. Nothing else in this
 *    file adds speech, so the output can never contain doubled narration.
 *  - spec.music (optional) is mixed under the narration at spec.music.gain_db.
 *  - clips are trimmed/scaled to spec.resolution and concatenated in order.
 *  - captions are burned in from a generated .ass subtitle file.
 *  - output is H.264 (yuv420p) + AAC at spec.fps, exactly spec.resolution.
 *
 * If any stage fails the error is thrown with FFmpeg's own stderr tail so the
 * dashboard can show a real reason. Nothing is ever faked.
 */

const FFMPEG = process.env.FFMPEG_PATH || "ffmpeg";
const FFPROBE = process.env.FFPROBE_PATH || "ffprobe";

export function run(cmd, args, { onLine } = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(cmd, args, { stdio: ["ignore", "pipe", "pipe"] });
    let out = "";
    let err = "";
    child.stdout.on("data", (d) => {
      out += d.toString();
    });
    child.stderr.on("data", (d) => {
      const text = d.toString();
      err += text;
      if (err.length > 200_000) err = err.slice(-100_000);
      if (onLine) for (const line of text.split(/\r|\n/)) if (line.trim()) onLine(line);
    });
    child.on("error", (e) => reject(new Error(`${cmd} could not start: ${e.message}`)));
    child.on("close", (code) => {
      if (code === 0) resolve({ stdout: out, stderr: err });
      else reject(new Error(`${cmd} exited with code ${code}: ${err.trim().split("\n").slice(-8).join(" | ")}`));
    });
  });
}

async function download(url, dest) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Download failed (${res.status}) for ${url.split("?")[0]}`);
  const buf = Buffer.from(await res.arrayBuffer());
  if (!buf.length) throw new Error(`Downloaded an empty file from ${url.split("?")[0]}`);
  await writeFile(dest, buf);
  return dest;
}

/**
 * Gated integrated loudness (EBU R128) of a file, used to place the music bed
 * under the speech. Gating matters: it ignores the pauses in the narration, so
 * the bed is positioned against actual speech level, not against silence.
 */
export async function probeLoudness(file) {
  const { stderr } = await run(FFMPEG, [
    "-hide_banner", "-i", file,
    "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
    "-vn", "-f", "null", "-",
  ]);
  const start = stderr.lastIndexOf("{");
  const end = stderr.lastIndexOf("}");
  if (start >= 0 && end > start) {
    try {
      const parsed = JSON.parse(stderr.slice(start, end + 1));
      const i = Number(parsed.input_i);
      if (Number.isFinite(i) && i > -70) return { lufs: i };
    } catch {
      /* fall through to the default below */
    }
  }
  return { lufs: -23 };
}

export async function probeDuration(file) {
  const { stdout } = await run(FFPROBE, [
    "-v", "error",
    "-show_entries", "format=duration",
    "-of", "default=noprint_wrappers=1:nokey=1",
    file,
  ]);
  const value = Number.parseFloat(stdout.trim());
  return Number.isFinite(value) ? value : 0;
}

function assTime(seconds) {
  const s = Math.max(0, seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = (s % 60).toFixed(2).padStart(5, "0");
  return `${h}:${String(m).padStart(2, "0")}:${sec}`;
}

function escapeAss(text) {
  return String(text).replace(/\\/g, "\\\\").replace(/\{/g, "(").replace(/\}/g, ")").replace(/\r?\n/g, "\\N");
}

/** Hard-wrap caption text so nothing overflows the frame width. */
function wrapCaption(text, maxChars = 26) {
  const words = String(text).split(/\s+/).filter(Boolean);
  const out = [];
  let line = "";
  for (const w of words) {
    if (line && (line + " " + w).length > maxChars) {
      out.push(line);
      line = w;
    } else {
      line = line ? `${line} ${w}` : w;
    }
  }
  if (line) out.push(line);
  return out.join("\\N");
}

/** Burned-in captions + persistent branding, built as one ASS subtitle file. */
function buildAss(spec, totalDuration) {
  const { width, height } = spec.resolution;
  const fontSize = Math.round(height * 0.042);
  const brandSize = Math.round(height * 0.024);
  const lines = [
    "[Script Info]",
    "ScriptType: v4.00+",
    `PlayResX: ${width}`,
    `PlayResY: ${height}`,
    "WrapStyle: 0",
    "",
    "[V4+ Styles]",
    "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
    `Style: Caption,DejaVu Sans,${fontSize},&H00FFFFFF,&H00101010,&H80000000,1,3,${Math.round(fontSize * 0.12)},2,2,${Math.round(width * 0.08)},${Math.round(width * 0.08)},${Math.round(height * 0.16)},1`,
    `Style: Brand,DejaVu Sans,${brandSize},&H00FFFFFF,&H00101010,&H80000000,1,3,2,1,9,${Math.round(width * 0.04)},${Math.round(width * 0.04)},${Math.round(height * 0.03)},1`,
    `Style: Lower,DejaVu Sans,${brandSize},&H00FFFFFF,&H00101010,&H80000000,0,3,2,1,1,${Math.round(width * 0.05)},${Math.round(width * 0.05)},${Math.round(height * 0.08)},1`,
    "",
    "[Events]",
    "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
  ];

  for (const cue of spec.captions ?? []) {
    if (!cue?.text) continue;
    const start = Number(cue.start ?? 0);
    const end = Number(cue.end ?? start + 2.5);
    if (!(end > start)) continue;
    lines.push(`Dialogue: 0,${assTime(start)},${assTime(end)},Caption,,0,0,0,,${wrapCaption(escapeAss(cue.text))}`);
  }

  const brand = spec.branding ?? {};
  if (brand.logo_text) {
    lines.push(`Dialogue: 1,${assTime(0)},${assTime(totalDuration)},Brand,,0,0,0,,${escapeAss(brand.logo_text)}`);
  }
  if (brand.lower_third) {
    lines.push(`Dialogue: 1,${assTime(0)},${assTime(Math.min(5, totalDuration))},Lower,,0,0,0,,${escapeAss(brand.lower_third)}`);
  }
  if (brand.disclaimer) {
    const from = Math.max(0, totalDuration - (brand.outro_sec ?? 2) - 3);
    lines.push(`Dialogue: 1,${assTime(from)},${assTime(totalDuration)},Lower,,0,0,0,,${escapeAss(brand.disclaimer)}`);
  }
  if (brand.outro_text) {
    const from = Math.max(0, totalDuration - (brand.outro_sec ?? 2));
    lines.push(`Dialogue: 1,${assTime(from)},${assTime(totalDuration)},Caption,,0,0,0,,${escapeAss(brand.outro_text)}`);
  }
  return lines.join("\n");
}

function ffEscapePath(p) {
  return p.replace(/\\/g, "/").replace(/:/g, "\\:").replace(/'/g, "\\'");
}

/**
 * Render one job.
 * @returns {{videoFile: string, thumbFile: string, durationSec: number, sizeBytes: number, cleanup: () => Promise<void>}}
 */
export async function renderSpec(spec, { onProgress } = {}) {
  const dir = await mkdtemp(path.join(tmpdir(), "thraansh-"));
  const cleanup = () => rm(dir, { recursive: true, force: true });
  const progress = (p) => onProgress && onProgress(Math.max(0, Math.min(99, Math.round(p))));

  try {
    const { width, height } = spec.resolution ?? { width: 1080, height: 1920 };
    const fps = spec.fps ?? 30;

    // 1. narration (the single speech track)
    let narrationFile = null;
    let narrationDuration = 0;
    if (spec.narration?.audio_url) {
      narrationFile = await download(spec.narration.audio_url, path.join(dir, "narration.audio"));
      narrationDuration = await probeDuration(narrationFile);
    }
    progress(10);

    const targetDuration = Math.max(
      5,
      narrationDuration > 0 ? narrationDuration + (spec.branding?.outro_sec ?? 2) : Number(spec.target_duration_sec ?? 45),
    );

    // 2. visual clips
    const clips = (spec.clips ?? []).filter((c) => c?.url);
    if (!clips.length) {
      throw new Error("Render spec contains no footage clips — approve footage for this story first");
    }
    const perClip = targetDuration / clips.length;
    const normalized = [];
    for (const [i, clip] of clips.entries()) {
      const src = await download(clip.url, path.join(dir, `clip-${i}.src`));
      const outFile = path.join(dir, `clip-${i}.mp4`);
      const zoom = clip.kenburns
        ? `,zoompan=z='min(zoom+0.0006,1.12)':d=${Math.round(perClip * fps)}:s=${width}x${height}:fps=${fps}`
        : "";
      // Always aspect-preserving: scale up until the frame is covered, then crop.
      // Never scale=W:H alone, which would stretch the source.
      // Off-orientation sources (landscape footage in a 9:16 composition) are
      // reframed with an upper-biased crop so faces/horizons survive the cut.
      const cropY = clip.reframe === "reframe" ? "(ih-oh)*0.35" : "(ih-oh)/2";
      const filter =
        `scale=${width}:${height}:force_original_aspect_ratio=increase,` +
        `crop=${width}:${height}:(iw-ow)/2:${cropY},setsar=1,fps=${fps}${zoom}`;
      // -loop only exists on the image demuxer; passing it for a video input
      // makes ffmpeg abort with "Option loop not found".
      const isStill = /\.(jpe?g|png|webp)$/i.test(clip.url.split("?")[0]);
      await run(FFMPEG, [
        "-y", "-hide_banner",
        ...(isStill ? ["-loop", "1"] : []),
        "-i", src,
        "-t", String(perClip.toFixed(3)),
        "-an",
        "-vf", filter,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
        outFile,
      ]);

      normalized.push(outFile);
      progress(10 + ((i + 1) / clips.length) * 40);
    }

    // 3. concatenate the visuals
    const listFile = path.join(dir, "clips.txt");
    await writeFile(listFile, normalized.map((f) => `file '${f.replace(/'/g, "'\\''")}'`).join("\n"));
    const silentVideo = path.join(dir, "visual.mp4");
    await run(FFMPEG, ["-y", "-hide_banner", "-f", "concat", "-safe", "0", "-i", listFile, "-c", "copy", silentVideo]);
    progress(55);

    // 4. captions + branding overlay
    const assFile = path.join(dir, "captions.ass");
    await writeFile(assFile, buildAss(spec, targetDuration));

    // 5. audio: narration (once) + optional music bed
    let musicFile = null;
    if (spec.music?.url) {
      try {
        musicFile = await download(spec.music.url, path.join(dir, "music.audio"));
      } catch {
        musicFile = null; // music is optional; never fail a render over the bed
      }
    }

    const music = spec.music && musicFile ? spec.music : null;
    const args = ["-y", "-hide_banner", "-i", silentVideo];
    if (narrationFile) args.push("-i", narrationFile);
    // -stream_loop makes the bed repeat so it never stops before the video ends.
    if (musicFile) args.push(...(music?.loop === false ? [] : ["-stream_loop", "-1"]), "-i", musicFile);

    const narrationIdx = narrationFile ? 1 : null;
    const musicIdx = musicFile ? (narrationFile ? 2 : 1) : null;

    const filters = [`[0:v]subtitles='${ffEscapePath(assFile)}'[v]`];
    const dur = Number(targetDuration.toFixed(3));
    const FMT = "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo";
    // The bed is placed RELATIVE to the measured narration level, so a quiet or
    // loud source track always ends up the same distance under the speech.
    let bedGainDb = music?.gain_db ?? -22;
    if (music && narrationFile) {
      const [narr, bed] = await Promise.all([probeLoudness(narrationFile), probeLoudness(musicFile)]);
      const below = Number(music.below_narration_db ?? 20);
      bedGainDb = Math.max(-40, Math.min(6, narr.lufs - below - bed.lufs));
    }
    const bedGain = Math.pow(10, bedGainDb / 20).toFixed(4);
    const fadeIn = Math.max(0, Number(music?.fade_in_sec ?? 1.5));
    const fadeOut = Math.max(0, Number(music?.fade_out_sec ?? 2.5));
    let audioMap = null;

    if (narrationIdx !== null && musicIdx !== null) {
      // Narration is padded to the full duration so the mix never truncates
      // early, and split so a copy can drive the ducking sidechain.
      filters.push(
        `[${narrationIdx}:a]${FMT},apad,atrim=0:${dur},asetpts=N/SR/TB,asplit=2[nar][key]`,
        `[${musicIdx}:a]${FMT},atrim=0:${dur},asetpts=N/SR/TB,volume=${bedGain}` +
          (fadeIn > 0 ? `,afade=t=in:st=0:d=${fadeIn}` : "") +
          (fadeOut > 0 ? `,afade=t=out:st=${Math.max(0, dur - fadeOut).toFixed(3)}:d=${fadeOut}` : "") +
          `[bedraw]`,
      );
      if (music?.duck === false) {
        filters.push(`[bedraw]anull[bed]`);
      } else {
        // Smooth sidechain ducking. The duck depth follows duck_reduction_db,
        // the soft knee + slow release stop the bed from pumping, and the
        // 450 ms release lets music breathe back up in short speech gaps
        // without ever climbing over a word.
        const reduction = Math.max(6, Math.min(18, Number(music?.duck_reduction_db ?? 10)));
        const ratio = Math.max(3, Math.min(10, Number((2 + reduction / 2).toFixed(1))));
        filters.push(
          `[bedraw][key]sidechaincompress=threshold=0.03:ratio=${ratio}:attack=20:release=450:knee=6:makeup=1:level_sc=1[bed]`,
        );
      }

      filters.push(
        `[nar][bed]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[mixraw]`,
        `[mixraw]alimiter=limit=0.95:level=disabled,${FMT}[a]`,
      );
      audioMap = "[a]";
    } else if (narrationIdx !== null) {
      filters.push(`[${narrationIdx}:a]${FMT},apad,atrim=0:${dur},asetpts=N/SR/TB[a]`);
      audioMap = "[a]";
    } else if (musicIdx !== null) {
      filters.push(`[${musicIdx}:a]${FMT},atrim=0:${dur},asetpts=N/SR/TB,volume=${bedGain}[a]`);
      audioMap = "[a]";
    }

    const videoFile = path.join(dir, "final.mp4");
    args.push("-filter_complex", filters.join(";"), "-map", "[v]");
    if (audioMap) args.push("-map", audioMap);
    args.push(
      "-t", String(targetDuration.toFixed(3)),
      "-r", String(fps),
      "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
      "-profile:v", "high", "-level", "4.1",
      "-movflags", "+faststart",
    );
    if (audioMap) args.push("-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2");
    else args.push("-an");
    args.push(videoFile);

    await run(FFMPEG, args, {
      onLine: (line) => {
        const m = /time=(\d+):(\d+):(\d+\.?\d*)/.exec(line);
        if (!m) return;
        const secs = Number(m[1]) * 3600 + Number(m[2]) * 60 + Number(m[3]);
        progress(55 + (secs / targetDuration) * 35);
      },
    });
    progress(92);

    // 6. thumbnail from the configured clip position
    const thumbFile = path.join(dir, "thumb.jpg");
    const thumbAt = Math.min(targetDuration - 0.5, Math.max(0.5, perClip * (spec.thumbnail?.background_clip_index ?? 0) + perClip / 2));
    await run(FFMPEG, [
      "-y", "-hide_banner",
      "-ss", String(thumbAt.toFixed(2)),
      "-i", videoFile,
      "-frames:v", "1",
      "-vf", `scale=${width}:${height}`,
      "-q:v", "3",
      thumbFile,
    ]);

    const [durationSec, info] = await Promise.all([probeDuration(videoFile), stat(videoFile)]);
    progress(98);
    return { videoFile, thumbFile, durationSec, sizeBytes: info.size, cleanup };
  } catch (err) {
    await cleanup();
    throw err;
  }
}
