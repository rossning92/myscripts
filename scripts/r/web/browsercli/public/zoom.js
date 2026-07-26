export function setupScreencastZoom(stage, canvas, { maxScale = 4 } = {}) {
  let scale = 1;
  let panX = 0;
  let panY = 0;
  let pinch = null;
  let panTouch = null;

  canvas.style.transformOrigin = "0 0";
  canvas.style.willChange = "transform";

  // Some mobile browsers leave the layout viewport at its original height
  // when the on-screen keyboard opens and only resize visualViewport.
  function syncVisualViewport() {
    const viewport = window.visualViewport;
    const height = viewport ? viewport.height : window.innerHeight;
    document.documentElement.style.setProperty(
      "--visual-viewport-height",
      `${height}px`
    );
  }

  syncVisualViewport();
  window.addEventListener("resize", syncVisualViewport);
  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", syncVisualViewport);
    window.visualViewport.addEventListener("scroll", syncVisualViewport);
  }

  function distance(a, b) {
    return Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
  }

  function midpoint(a, b) {
    return {
      x: (a.clientX + b.clientX) / 2,
      y: (a.clientY + b.clientY) / 2,
    };
  }

  function clampView() {
    const stageRect = stage.getBoundingClientRect();
    const width = canvas.offsetWidth * scale;
    const height = canvas.offsetHeight * scale;
    const baseX = canvas.offsetLeft;
    const baseY = canvas.offsetTop;

    if (width <= stageRect.width) {
      panX = (stageRect.width - width) / 2 - baseX;
    } else {
      panX = Math.min(
        -baseX,
        Math.max(stageRect.width - baseX - width, panX)
      );
    }

    if (height <= stageRect.height) {
      panY = (stageRect.height - height) / 2 - baseY;
    } else {
      panY = Math.min(
        -baseY,
        Math.max(stageRect.height - baseY - height, panY)
      );
    }
  }

  function render() {
    if (scale === 1) {
      panX = 0;
      panY = 0;
    } else {
      clampView();
    }
    canvas.style.transform = `translate(${panX}px, ${panY}px) scale(${scale})`;
  }

  stage.addEventListener(
    "touchstart",
    (event) => {
      if (event.touches.length === 2) {
        event.preventDefault();
        const stageRect = stage.getBoundingClientRect();
        const mid = midpoint(event.touches[0], event.touches[1]);
        pinch = {
          distance: distance(event.touches[0], event.touches[1]),
          scale,
          contentX:
            (mid.x - stageRect.left - canvas.offsetLeft - panX) / scale,
          contentY:
            (mid.y - stageRect.top - canvas.offsetTop - panY) / scale,
        };
        panTouch = null;
      } else if (event.touches.length === 1 && scale > 1) {
        panTouch = {
          x: event.touches[0].clientX,
          y: event.touches[0].clientY,
          panX,
          panY,
        };
      }
    },
    { passive: false }
  );

  stage.addEventListener(
    "touchmove",
    (event) => {
      if (event.touches.length === 2 && pinch) {
        event.preventDefault();
        const stageRect = stage.getBoundingClientRect();
        const mid = midpoint(event.touches[0], event.touches[1]);
        scale = Math.min(
          maxScale,
          Math.max(
            1,
            pinch.scale *
              (distance(event.touches[0], event.touches[1]) / pinch.distance)
          )
        );
        panX =
          mid.x -
          stageRect.left -
          canvas.offsetLeft -
          pinch.contentX * scale;
        panY =
          mid.y -
          stageRect.top -
          canvas.offsetTop -
          pinch.contentY * scale;
        render();
      } else if (
        event.touches.length === 1 &&
        panTouch &&
        scale > 1
      ) {
        event.preventDefault();
        panX = panTouch.panX + event.touches[0].clientX - panTouch.x;
        panY = panTouch.panY + event.touches[0].clientY - panTouch.y;
        render();
      }
    },
    { passive: false }
  );

  stage.addEventListener("touchend", (event) => {
    if (event.touches.length < 2) pinch = null;
    if (event.touches.length === 1 && scale > 1) {
      panTouch = {
        x: event.touches[0].clientX,
        y: event.touches[0].clientY,
        panX,
        panY,
      };
    } else if (event.touches.length === 0) {
      panTouch = null;
    }
  });

  stage.addEventListener("touchcancel", () => {
    pinch = null;
    panTouch = null;
  });

  // Safari exposes this separately even with a restrictive viewport.
  document.addEventListener("gesturestart", (event) => event.preventDefault());
  window.addEventListener("resize", render);

  // visualViewport changes (notably the mobile keyboard opening) can resize
  // the stage without firing a window resize event.
  if ("ResizeObserver" in window) {
    new ResizeObserver(render).observe(stage);
  }
}
