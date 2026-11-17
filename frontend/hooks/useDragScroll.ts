import { useEffect, useRef } from "react";

const DRAG_THRESHOLD_PX = 5;

/**
 * Lets a scrollable box be panned by dragging it with the mouse or a finger. A click that is really the end of a drag is swallowed,
 * so letting go over a box in an org chart does not select it.
 */
export function useDragScroll<T extends HTMLElement>() {
  const ref = useRef<T>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    let isDown = false;
    let hasMoved = false;
    let startX = 0;
    let startY = 0;
    let startLeft = 0;
    let startTop = 0;

    function onDown(event: PointerEvent) {
      if (event.button !== 0 || !element) return;
      isDown = true;
      hasMoved = false;
      startX = event.clientX;
      startY = event.clientY;
      startLeft = element.scrollLeft;
      startTop = element.scrollTop;
    }
    function onMove(event: PointerEvent) {
      if (!isDown || !element) return;
      const deltaX = event.clientX - startX;
      const deltaY = event.clientY - startY;
      if (!hasMoved && Math.hypot(deltaX, deltaY) < DRAG_THRESHOLD_PX) return;
      hasMoved = true;
      element.scrollLeft = startLeft - deltaX;
      element.scrollTop = startTop - deltaY;
      element.style.cursor = "grabbing";
    }
    function onUp() {
      isDown = false;
      if (element) element.style.cursor = "";
    }
    function onClickCapture(event: MouseEvent) {
      if (!hasMoved) return;
      event.stopPropagation();
      event.preventDefault();
      hasMoved = false;
    }

    element.addEventListener("pointerdown", onDown);
    element.addEventListener("click", onClickCapture, true);
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      element.removeEventListener("pointerdown", onDown);
      element.removeEventListener("click", onClickCapture, true);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, []);

  return ref;
}
