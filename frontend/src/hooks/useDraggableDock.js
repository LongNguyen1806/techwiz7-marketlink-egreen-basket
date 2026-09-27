import { useCallback, useEffect, useRef, useState } from 'react';
import { useDragControls, useMotionValue } from 'framer-motion';

const STORAGE_KEY = 'marketlink.chat-dock';
// How far a pointer may travel before the gesture counts as a drag rather than a tap. Below
// this, a slightly shaky click still opens the panel.
const DRAG_SLOP = 4;
const NO_ROOM = { left: 0, right: 0, top: 0, bottom: 0 };

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

// How far the element may travel from its corner. The anchor is the bottom-right, so every
// allowed offset is zero or negative.
function roomFor(size, margin) {
  if (typeof window === 'undefined') return NO_ROOM;
  return {
    left: -Math.max(0, window.innerWidth - size - margin * 2),
    right: 0,
    top: -Math.max(0, window.innerHeight - size - margin * 2),
    bottom: 0,
  };
}

function readStored() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? 'null');
    if (typeof parsed?.x === 'number' && typeof parsed?.y === 'number') return parsed;
  } catch {
    // A private window, or blocked site data. The dock simply starts where it always did.
  }
  return { x: 0, y: 0 };
}

/**
 * Lets a floating element be dragged anywhere on screen and remembers where it was left.
 *
 * The element stays anchored to its CSS corner and moves by a translation, rather than having
 * its `left`/`top` rewritten. Dragging already works by translating the element, so writing a
 * new position on drop would apply the movement twice and make the thing jump.
 *
 * `size` is the element's side in pixels and `margin` the gap it keeps from every edge; both
 * are what the offsets are clamped against, so the dock can never be dragged out of reach.
 */
export function useDraggableDock({ size = 56, margin = 16 } = {}) {
  // Measured up front rather than in an effect: the window is there on the first render, and
  // a remembered position that has not been clamped yet would put the dock off-screen for
  // one frame on a window narrower than the one it was left on.
  const [constraints, setConstraints] = useState(() => roomFor(size, margin));
  const [initial] = useState(() => {
    const stored = readStored();
    const room = roomFor(size, margin);
    return { x: clamp(stored.x, room.left, 0), y: clamp(stored.y, room.top, 0) };
  });
  // Drags start from a named handle rather than from anywhere on the element, so a press on
  // the close button or inside the text box is not mistaken for one.
  const dragControls = useDragControls();
  const x = useMotionValue(initial.x);
  const y = useMotionValue(initial.y);
  const dragged = useRef(false);

  const measure = useCallback(() => {
    const room = roomFor(size, margin);
    setConstraints(room);
    // Rotating a phone or shrinking a window can leave the dock off-screen, so pull it back.
    x.set(clamp(x.get(), room.left, 0));
    y.set(clamp(y.get(), room.top, 0));
  }, [margin, size, x, y]);

  useEffect(() => {
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, [measure]);

  const dragProps = {
    drag: true,
    dragListener: false,
    dragControls,
    dragConstraints: constraints,
    dragMomentum: false,
    dragElastic: 0,
    style: { x, y },
    onDrag: (_event, info) => {
      if (Math.abs(info.offset.x) > DRAG_SLOP || Math.abs(info.offset.y) > DRAG_SLOP) {
        dragged.current = true;
      }
    },
    onDragEnd: () => {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ x: x.get(), y: y.get() }));
      } catch {
        // Not worth interrupting the drag over; the dock just forgets on the next reload.
      }
    },
  };

  const startDrag = (event) => {
    dragged.current = false;
    dragControls.start(event);
  };

  // Called from the click handler: a drop still fires a click, and without this, every time
  // the button was moved it would also open.
  const wasDragged = () => dragged.current;

  return { dragProps, startDrag, wasDragged };
}
