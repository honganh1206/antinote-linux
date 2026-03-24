import { getCurrentWindow, currentMonitor } from "@tauri-apps/api/window";
import { PhysicalPosition, PhysicalSize } from "@tauri-apps/api/dpi";
import { getSetting, setSetting } from "./db";

interface WindowGeometry {
  x: number;
  y: number;
  width: number;
  height: number;
}

const SETTING_KEY = "window_geometry";
const DEBOUNCE_MS = 500;
const MIN_WIDTH = 360;
const MIN_HEIGHT = 360;

let saveTimer: ReturnType<typeof setTimeout> | null = null;

function scheduleGeometrySave(geometry: WindowGeometry) {
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    setSetting(SETTING_KEY, JSON.stringify(geometry));
  }, DEBOUNCE_MS);
}

async function isOnScreen(geometry: WindowGeometry): Promise<boolean> {
  const monitor = await currentMonitor();
  if (!monitor) return false;

  const { x: mx, y: my } = monitor.position;
  const { width: mw, height: mh } = monitor.size;

  const windowRight = geometry.x + geometry.width;
  const windowBottom = geometry.y + geometry.height;
  const monitorRight = mx + mw;
  const monitorBottom = my + mh;

  const overlapX = Math.max(0, Math.min(windowRight, monitorRight) - Math.max(geometry.x, mx));
  const overlapY = Math.max(0, Math.min(windowBottom, monitorBottom) - Math.max(geometry.y, my));

  return overlapX >= 50 && overlapY >= 50;
}

export async function restoreWindowGeometry(): Promise<void> {
  const raw = await getSetting(SETTING_KEY);
  if (!raw) return;

  let geometry: WindowGeometry;
  try {
    geometry = JSON.parse(raw);
  } catch {
    return;
  }

  if (
    typeof geometry.x !== "number" ||
    typeof geometry.y !== "number" ||
    typeof geometry.width !== "number" ||
    typeof geometry.height !== "number"
  ) {
    return;
  }

  geometry.width = Math.max(geometry.width, MIN_WIDTH);
  geometry.height = Math.max(geometry.height, MIN_HEIGHT);

  if (!(await isOnScreen(geometry))) return;

  const appWindow = getCurrentWindow();
  await appWindow.setSize(new PhysicalSize(geometry.width, geometry.height));
  await appWindow.setPosition(new PhysicalPosition(geometry.x, geometry.y));
}

export async function trackWindowGeometry(): Promise<() => void> {
  const appWindow = getCurrentWindow();

  let currentGeometry: WindowGeometry = {
    x: 0,
    y: 0,
    width: 400,
    height: 400,
  };

  const pos = await appWindow.outerPosition();
  const size = await appWindow.outerSize();
  currentGeometry = { x: pos.x, y: pos.y, width: size.width, height: size.height };

  const unlistenMove = await appWindow.onMoved(({ payload: position }) => {
    currentGeometry.x = position.x;
    currentGeometry.y = position.y;
    scheduleGeometrySave(currentGeometry);
  });

  const unlistenResize = await appWindow.onResized(({ payload: size }) => {
    currentGeometry.width = size.width;
    currentGeometry.height = size.height;
    scheduleGeometrySave(currentGeometry);
  });

  return () => {
    unlistenMove();
    unlistenResize();
    if (saveTimer) {
      clearTimeout(saveTimer);
      saveTimer = null;
    }
  };
}
