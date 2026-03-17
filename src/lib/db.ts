import Database from "@tauri-apps/plugin-sql";
import type { Note } from "./types";

const DB_PATH = "sqlite:notes.db";

let dbInstance: Database | null = null;

async function getDb(): Promise<Database> {
  if (!dbInstance) {
    dbInstance = await Database.load(DB_PATH);
    await dbInstance.execute("PRAGMA journal_mode=WAL");
    await dbInstance.execute("PRAGMA busy_timeout=3000");
  }
  return dbInstance;
}

export async function getAllNotes(): Promise<Note[]> {
  const db = await getDb();
  return db.select<Note[]>("SELECT * FROM notes ORDER BY sort_index ASC");
}

export async function getNote(id: number): Promise<Note | null> {
  const db = await getDb();
  const rows = await db.select<Note[]>(
    "SELECT * FROM notes WHERE id = $1",
    [id]
  );
  return rows[0] ?? null;
}

export async function createNote(content: string = ""): Promise<Note> {
  const db = await getDb();
  const now = Date.now();

  const maxResult = await db.select<{ max_idx: number | null }[]>(
    "SELECT MAX(sort_index) as max_idx FROM notes"
  );
  const nextIndex = (maxResult[0]?.max_idx ?? 0) + 1;

  const result = await db.execute(
    "INSERT INTO notes (content, sort_index, created_at, updated_at) VALUES ($1, $2, $3, $4)",
    [content, nextIndex, now, now]
  );

  return {
    id: result.lastInsertId,
    content,
    sort_index: nextIndex,
    created_at: now,
    updated_at: now,
  };
}

export async function updateNoteContent(
  id: number,
  content: string
): Promise<void> {
  const db = await getDb();
  const now = Date.now();
  await db.execute(
    "UPDATE notes SET content = $1, updated_at = $2 WHERE id = $3",
    [content, now, id]
  );
}

export async function deleteNote(id: number): Promise<void> {
  const db = await getDb();
  await db.execute("DELETE FROM notes WHERE id = $1", [id]);
}

export async function getSetting(key: string): Promise<string | null> {
  const db = await getDb();
  const rows = await db.select<{ value: string }[]>(
    "SELECT value FROM app_settings WHERE key = $1",
    [key]
  );
  return rows[0]?.value ?? null;
}

export async function setSetting(key: string, value: string): Promise<void> {
  const db = await getDb();
  await db.execute(
    "INSERT INTO app_settings (key, value) VALUES ($1, $2) ON CONFLICT(key) DO UPDATE SET value = $2",
    [key, value]
  );
}
