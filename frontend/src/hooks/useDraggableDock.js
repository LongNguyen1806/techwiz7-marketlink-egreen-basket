import { useCallback, useEffect, useRef, useState } from 'react';
import { useDragControls, useMotionValue } from 'framer-motion';

const STORAGE_KEY = 'marketlink.chat-dock';
const DRAG_SLOP = 4;
const NO_ROOM = { left: 0, right: 0, top: 0, bottom: 0 };

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

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
  }
  return { x: 0, y: 0 };
}

export function useDraggableDock({ size = 56, margin = 16 } = {}) {
  const [constraints, setConstraints] = useState(() => roomFor(size, margin));
  const [initial] = useState(() => {
    const stored = readStored();
    const room = roomFor(size, margin);
    return { x: clamp(stored.x, room.left, 0), y: clamp(stored.y, room.top, 0) };
  });
  const dragControls = useDragControls();
  const x = useMotionValue(initial.x);
  const y = useMotionValue(initial.y);
  const dragged = useRef(false);

  const measure = useCallback(() => {
    const room = roomFor(size, margin);
    setConstraints(room);
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
      }
    },
  };

  const startDrag = (event) => {
    dragged.current = false;
    dragControls.start(event);
  };

  const wasDragged = () => dragged.current;

  return { dragProps, startDrag, wasDragged };
}
