import { spawn } from "child_process";
import { once } from "events";
import { CdpConnection } from "../browser/cdp-client.js";

const audioRate = 48000;
const audioChannels = 2;
const audioFrameMs = 10;
const audioFrames = audioRate * audioFrameMs / 1000;
const initialAudioPackets = 3;
const maxAudioPackets = 8;

function captureAudio(sink, source, signal, onFailure) {
  const capture = spawn("parec", [
    `--device=${sink}.monitor`,
    "--raw", `--rate=${audioRate}`, `--channels=${audioChannels}`, "--format=s16le",
    "--latency-msec=20", "--process-time-msec=10",
  ], { stdio: ["ignore", "pipe", "ignore"] });
  const silence = new Int16Array(audioFrames * audioChannels);
  const packet = Buffer.alloc(silence.byteLength);
  const queue = [];
  let used = 0;
  let timer;
  let nextFrameTime;

  // Pipe reads can deliver several frames at once. Feed WebRTC on the audio
  // clock, and bound the queue so a pause cannot turn into delayed playback.
  function sendFrame() {
    source.onData({
      samples: queue.shift() ?? silence,
      sampleRate: audioRate,
      channelCount: audioChannels,
      numberOfFrames: audioFrames,
    });
    const now = performance.now();
    nextFrameTime = Math.max(nextFrameTime + audioFrameMs, now + 1);
    timer = setTimeout(sendFrame, nextFrameTime - now);
  }

  signal.addEventListener("abort", () => {
    clearTimeout(timer);
    capture.kill();
  }, { once: true });
  capture.once("error", onFailure);
  capture.once("close", onFailure);
  capture.stdout.on("data", (chunk) => {
    for (let offset = 0; offset < chunk.length && !signal.aborted;) {
      const copied = chunk.copy(packet, used, offset, offset + packet.length - used);
      offset += copied;
      used += copied;
      if (used !== packet.length) continue;
      const samples = new Int16Array(silence.length);
      Buffer.from(samples.buffer).set(packet);
      if (queue.length === maxAudioPackets) queue.shift();
      queue.push(samples);
      used = 0;
    }
    if (timer === undefined && queue.length >= initialAudioPackets) {
      nextFrameTime = performance.now();
      sendFrame();
    }
  });
}

async function captureVideo(url, source, sharp, rgbaToI420, signal, onFailure) {
  const cdp = await new CdpConnection(url).connect();
  if (signal.aborted) {
    cdp.close();
    signal.throwIfAborted();
  }

  let latestJpeg;
  let lastFrame;
  let decoding = false;

  async function sendFrame() {
    if (decoding || !latestJpeg || signal.aborted) return;
    decoding = true;
    try {
      while (latestJpeg && !signal.aborted) {
        const jpeg = latestJpeg;
        latestJpeg = undefined;
        const { data, info: { width, height } } = await sharp(jpeg)
          .ensureAlpha().raw().toBuffer({ resolveWithObject: true });
        if (signal.aborted) return;
        const rgba = new Uint8ClampedArray(data.buffer, data.byteOffset, data.byteLength);
        const chromaSize = Math.ceil(width / 2) * Math.ceil(height / 2);
        lastFrame = { width, height, data: new Uint8ClampedArray(width * height + 2 * chromaSize) };
        rgbaToI420({ width, height, data: rgba }, lastFrame);
        source.onFrame(lastFrame);
      }
    } catch {
      onFailure();
    } finally {
      decoding = false;
    }
  }

  // Repeat still frames so receivers can start and recover without a page repaint.
  const repeat = setInterval(() => {
    if (!decoding && lastFrame) source.onFrame(lastFrame);
  }, 200);
  signal.addEventListener("abort", () => {
    clearInterval(repeat);
    cdp.close();
  }, { once: true });
  cdp.once("disconnected", onFailure);
  cdp.on("Page.screencastFrame", ({ data, sessionId }) => {
    latestJpeg = Buffer.from(data, "base64");
    cdp.send("Page.screencastFrameAck", { sessionId }).catch(onFailure);
    void sendFrame();
  });
  await cdp.send("Page.startScreencast", { format: "jpeg", quality: 80, everyNthFrame: 1 });
}

async function startScreencastSender({ url, sink, offer, signal, onFailure }) {
  const [{ default: wrtc }, { default: sharp }] = await Promise.all([
    import("@roamhq/wrtc"),
    import("sharp"),
  ]);
  signal.throwIfAborted();

  const { RTCAudioSource, RTCVideoSource, rgbaToI420 } = wrtc.nonstandard;
  const peer = new wrtc.RTCPeerConnection({ iceServers: [] });
  const video = new RTCVideoSource({ isScreencast: true });
  const audio = new RTCAudioSource();
  const tracks = [video.createTrack(), audio.createTrack()];
  const stream = new wrtc.MediaStream(tracks);
  signal.addEventListener("abort", () => {
    for (const track of tracks) track.stop();
    peer.close();
  }, { once: true });
  peer.onconnectionstatechange = () => {
    if (peer.connectionState === "failed") onFailure();
  };

  await peer.setRemoteDescription({ type: "offer", sdp: offer.sdp });
  for (const track of tracks) peer.addTrack(track, stream);
  await peer.setLocalDescription(await peer.createAnswer());
  while (peer.iceGatheringState !== "complete") {
    await once(peer, "icegatheringstatechange", { signal });
  }
  signal.throwIfAborted();
  captureAudio(sink, audio, signal, onFailure);
  await captureVideo(url, video, sharp, rgbaToI420, signal, onFailure);
  return peer.localDescription;
}

const controller = new AbortController();
process.once("disconnect", () => controller.abort());
process.once("message", async ({ url, sink, offer }) => {
  try {
    const answer = await startScreencastSender({
      url, sink, offer,
      signal: controller.signal,
      onFailure: () => {
        if (process.connected) process.disconnect();
      },
    });
    if (process.connected) {
      process.send({ answer: { type: answer.type, sdp: answer.sdp } });
    }
  } catch (error) {
    if (!process.connected) return;
    console.error("Could not start screencast", error);
    process.send({ error: true });
    process.disconnect();
  }
});
