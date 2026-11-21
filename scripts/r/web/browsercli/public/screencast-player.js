export function setupScreencastPlayer({ button, session, targetId, draw, onFailure }) {
  const url = new URL("/screencast/webrtc", location.href);
  url.protocol = location.protocol === "https:" ? "wss:" : "ws:";
  if (session) url.searchParams.set("session", session);

  const peer = new RTCPeerConnection({ iceServers: [], bundlePolicy: "max-bundle" });
  const socket = new WebSocket(url);
  const video = document.createElement("video");
  const stream = new MediaStream();
  video.srcObject = stream;
  video.playsInline = true;
  video.muted = button.getAttribute("aria-pressed") === "true";
  video.style.cssText = "position:fixed;width:1px;height:1px;opacity:0;pointer-events:none";
  document.body.append(video);

  button.disabled = true;
  let closed = false;
  let ready = false;
  let offerSent = false;
  let frameRequest;
  let disconnectTimeout;

  function close() {
    if (closed) return;
    closed = true;
    clearTimeout(deadline);
    clearTimeout(disconnectTimeout);
    if (frameRequest !== undefined) video.cancelVideoFrameCallback(frameRequest);
    button.removeEventListener("click", toggleMute);
    button.disabled = true;
    socket.close();
    peer.close();
    video.srcObject = null;
    video.remove();
  }

  function fail() {
    if (closed) return;
    close();
    onFailure();
  }

  function render() {
    if (!ready) {
      ready = true;
      clearTimeout(deadline);
    }
    draw(video, video.videoWidth, video.videoHeight);
    frameRequest = video.requestVideoFrameCallback(render);
  }

  function updateAudioButton() {
    button.setAttribute("aria-pressed", String(video.muted));
    button.title = `${video.muted ? "Unmute" : "Mute"} (Ctrl+A, then M)`;
    button.disabled = false;
  }

  async function toggleMute() {
    if (!video.muted) {
      video.muted = true;
      updateAudioButton();
      return;
    }
    button.disabled = true;
    video.muted = false;
    try {
      await video.play();
    } catch {
      if (closed) return;
      video.muted = true;
      await video.play().catch(fail);
    }
    if (!closed) updateAudioButton();
  }

  const deadline = setTimeout(fail, 22000);
  button.addEventListener("click", toggleMute);
  peer.addTransceiver("video", { direction: "recvonly" });
  peer.addTransceiver("audio", { direction: "recvonly" });
  peer.ontrack = ({ track }) => {
    stream.addTrack(track);
    if (stream.getTracks().length !== 2) return;
    video.play().catch(() => {
      video.muted = true;
      return video.play();
    }).then(() => {
      if (closed) return;
      updateAudioButton();
      if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && video.videoWidth) {
        render();
      } else {
        frameRequest = video.requestVideoFrameCallback(render);
      }
    }).catch(fail);
  };

  function sendOffer() {
    if (
      !offerSent &&
      peer.iceGatheringState === "complete" &&
      peer.localDescription &&
      socket.readyState === WebSocket.OPEN
    ) {
      offerSent = true;
      socket.send(JSON.stringify({ ...peer.localDescription.toJSON(), targetId }));
    }
  }

  socket.onopen = async () => {
    try {
      await peer.setLocalDescription(await peer.createOffer());
      sendOffer();
    } catch {
      fail();
    }
  };
  peer.onicegatheringstatechange = sendOffer;
  socket.onmessage = async ({ data }) => {
    try {
      await peer.setRemoteDescription(JSON.parse(data));
    } catch {
      fail();
    }
  };
  socket.onclose = fail;
  peer.onconnectionstatechange = () => {
    clearTimeout(disconnectTimeout);
    if (peer.connectionState === "failed") fail();
    if (peer.connectionState === "disconnected") {
      disconnectTimeout = setTimeout(fail, 4000);
    }
  };
  return close;
}
