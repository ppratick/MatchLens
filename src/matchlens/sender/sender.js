const [pair, secret] = location.hash.slice(1).split(":");
const epoch = crypto.randomUUID();
const $ = (id) => document.getElementById(id);
let recorder,
  stream,
  queue = [],
  sequence = 0,
  sending = false,
  finishing = false,
  wake,
  started = 0,
  points = [],
  referenceImage = "",
  blocked = false,
  finished = false,
  workerFailed = false;
const say = (text) => ($("status").textContent = text);
const request = async (path, body) => {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch(path, {
      method: body === undefined ? "GET" : "POST",
      headers: {
        "x-pair-secret": secret,
        "x-sender-epoch": epoch,
        ...(body instanceof Blob ? {} : { "Content-Type": "application/json" }),
      },
      body:
        body === undefined
          ? undefined
          : body instanceof Blob
            ? body
            : JSON.stringify(body),
      signal: controller.signal,
    });
    const result = await response.json();
    if (!response.ok) {
      const error = Error(result.detail || response.statusText);
      error.code = response.status;
      throw error;
    }
    return result;
  } finally {
    clearTimeout(timer);
  }
};
const health = (state) =>
  request("/health/" + pair, {
    state,
    elapsed_ms: performance.now() - started,
  }).catch(() => {});
async function status() {
  try {
    const s = await request("/status/" + pair);
    $("recording").textContent =
      `Mac: ${s.recording_state} · ${s.segments} committed playable segments · ${s.recorded_seconds.toFixed(1)} s · ${s.bytes} received bytes${s.error ? " · " + s.error : ""}`;
    if (s.error) workerFailed = true;
    if (!recorder && s.next_sequence > 0) {
      blocked = true;
      $("start").disabled = true;
      say(
        "This pairing already contains a recorder epoch. Create a new pairing on the Mac after a reload; timelines must not be joined silently.",
      );
    }
    if (s.error && recorder?.state === "recording") {
      workerFailed = true;
      recorder.pause();
      await health("paused");
      say(
        "Mac recording worker failed. Received bytes remain preserved. Finish and inspect recovery on the Mac.",
      );
    }
  } catch (e) {
    $("recording").textContent = "Mac connection not confirmed · " + e.message;
  }
}
async function send() {
  if (sending || blocked) return;
  sending = true;
  try {
    while ((queue.length || finishing) && !blocked && !finished) {
      try {
        if (!queue.length && finishing) {
          await request("/finish/" + pair, {});
          finished = true;
          say(
            "Received recording finalized on Mac. Verify committed playback and audio before closing.",
          );
          stream.getTracks().forEach((t) => t.stop());
          await wake?.release();
          await status();
          break;
        }
        const result = await request(
          "/ingest/" + pair + "/" + sequence,
          queue[0],
        );
        queue.shift();
        $("preserve").disabled = !queue.length;
        sequence = result.next_sequence;
        say("Sending · " + sequence + " chunks durably received on Mac");
        if (
          recorder.state === "paused" &&
          queue.length < 3 &&
          !finishing &&
          !workerFailed
        ) {
          await health("resumed");
          recorder.resume();
          say("Resumed after marked wall-time gap");
        }
      } catch (e) {
        say("Disconnected · buffered bytes retained, retrying. " + e.message);
        if ([400, 403, 404, 409, 413].includes(e.code)) {
          blocked = true;
          if (recorder.state !== "inactive") recorder.stop();
          say(
            "Receiver refused continuation. Create a new source; keep this page open to retain its unsent buffer. " +
              e.message,
          );
          break;
        }
        await new Promise((r) => setTimeout(r, 1500));
      }
    }
  } finally {
    sending = false;
  }
}
$("start").onclick = async () => {
  try {
    if (!pair || !secret)
      throw Error("Open the fresh pairing link from MatchLens");
    if (!window.isSecureContext)
      throw Error("A trusted HTTPS secure context is required");
    const s = await request("/status/" + pair);
    if (s.next_sequence > 0 || s.finished)
      throw Error("Used pairing: create a new source on the Mac");
    stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: { ideal: "environment" },
        width: { ideal: 1280 },
        height: { ideal: 720 },
        frameRate: { ideal: 30 },
      },
      audio: $("audio").checked,
    });
    $("preview").srcObject = stream;
    $("align").style.display = "block";
    $("start").disabled = true;
    $("reset").disabled = false;
    say("Camera preview only · mark the four television picture corners");
  } catch (e) {
    say(
      e.name === "NotAllowedError"
        ? "Camera/microphone denied. Grant permission manually, or uncheck microphone audio and retry."
        : e.message,
    );
  }
};
$("align").onclick = (e) => {
  if (recorder || points.length >= 4 || !stream) return;
  const r = $("preview").getBoundingClientRect();
  points.push([(e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height]);
  $("corners").innerHTML = points
    .map(
      ([x, y], i) =>
        `<circle class="point" cx="${x * 1000}" cy="${y * 1000}" r="10"/><text x="${x * 1000 + 12}" y="${y * 1000}" fill="#dbfa8d" font-size="28">${i + 1}</text>`,
    )
    .join("");
  $("record").disabled = points.length !== 4;
  say(points.length + "/4 corners marked · preview only");
};
$("reset").onclick = () => {
  points = [];
  $("corners").innerHTML = "";
  $("record").disabled = true;
};
$("record").onclick = async () => {
  try {
    const canvas = document.createElement("canvas"),
      v = $("preview");
    canvas.width = v.videoWidth;
    canvas.height = v.videoHeight;
    if (!canvas.width) throw Error("Camera preview is not ready");
    canvas.getContext("2d").drawImage(v, 0, 0);
    referenceImage = canvas.toDataURL("image/jpeg", 0.85);
    await request("/television/" + pair, {
      reference_image: referenceImage,
      calibration: { corners: points, start: 0, width: 1280, height: 720 },
    });
    const mime = [
      "video/webm;codecs=vp8,opus",
      "video/mp4;codecs=avc1.42E01E,mp4a.40.2",
      "video/mp4",
    ].find((m) => MediaRecorder.isTypeSupported(m));
    recorder = new MediaRecorder(stream, {
      ...(mime ? { mimeType: mime } : {}),
      videoBitsPerSecond: 4000000,
    });
    started = performance.now();
    recorder.ondataavailable = (e) => {
      if (e.data.size) {
        for (let a = 0; a < e.data.size; a += 8 * 1024 * 1024)
          queue.push(e.data.slice(a, a + 8 * 1024 * 1024));
        $("preserve").disabled = !queue.length;
        if (
          queue.reduce((s, b) => s + b.size, 0) > 24 * 1024 * 1024 &&
          recorder.state === "recording"
        ) {
          recorder.pause();
          health("paused");
          say("Buffer full · capture paused, interruption marked");
        }
        send();
      }
    };
    recorder.onstop = () => {
      finishing = true;
      send();
    };
    recorder.start(2000);
    $("record").disabled = true;
    $("reset").disabled = true;
    $("stop").disabled = false;
    say("Sending to Mac · verify committed segment status below");
    try {
      wake = await navigator.wakeLock.request("screen");
    } catch {}
    stream.getVideoTracks()[0].onended = () => {
      health("track_ended");
      if (recorder.state !== "inactive") recorder.stop();
    };
  } catch (e) {
    say(e.message);
  }
};
$("preserve").onclick = () => {
  if (!queue.length) return;
  const url = URL.createObjectURL(new Blob(queue));
  const a = document.createElement("a");
  a.href = url;
  a.download = `unsent-${pair}-from-chunk-${sequence}.bin`;
  a.click();
  URL.revokeObjectURL(url);
  say(
    "Raw unsent tail downloaded. Retain it with the Mac's received original; this tail alone may not be playable.",
  );
};
$("stop").onclick = () => {
  $("stop").disabled = true;
  if (recorder.state !== "inactive") recorder.stop();
};
document.addEventListener("visibilitychange", () => {
  if (document.hidden && recorder?.state !== "inactive" && recorder) {
    health("suspended");
    recorder.stop();
    say(
      "Phone page suspended: this source is ending. Create a new pairing before recording again.",
    );
  }
});
window.addEventListener("beforeunload", (e) => {
  if (recorder && !finished) {
    e.preventDefault();
    e.returnValue = "Recording or unsent bytes remain";
  }
});
setInterval(status, 2500);
status();
setInterval(() => {
  if (!stream) return;
  const v = $("preview"),
    c = document.createElement("canvas");
  c.width = 160;
  c.height = 90;
  const context = c.getContext("2d", { willReadFrequently: true });
  context.drawImage(v, 0, 0, 160, 90);
  const d = context.getImageData(0, 0, 160, 90).data;
  let light = 0,
    bright = 0,
    edge = 0;
  for (let i = 0; i < d.length; i += 4) {
    const l = (d[i] + d[i + 1] + d[i + 2]) / 3;
    light += l;
    if (l > 245) bright++;
    if (i >= 640)
      edge += Math.abs(l - (d[i - 640] + d[i - 639] + d[i - 638]) / 3);
  }
  const warnings = [];
  if (innerHeight > innerWidth)
    warnings.push("Rotate to landscape and recheck corners.");
  if (light / 14400 < 45)
    warnings.push("Low light: improve room lighting or exposure.");
  if (bright / 14400 > 0.18)
    warnings.push("Bright/glare regions: check reflections and exposure.");
  if (edge / 14400 < 3)
    warnings.push("Low detail/blur: stabilize the mount and check focus.");
  warnings.push(
    "Check TV borders, extreme angle, rolling bands/flicker, moire and people blocking the screen manually.",
  );
  $("warnings").textContent = warnings.join("\n");
}, 3000);
