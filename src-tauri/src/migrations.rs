use tauri_plugin_sql::{Migration, MigrationKind};

pub fn get_migrations() -> Vec<Migration> {
    vec![
        Migration {
            version: 1,
            description: "create_notes_and_settings",
            sql: "CREATE TABLE notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL DEFAULT '',
                sort_index INTEGER NOT NULL UNIQUE,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );
            CREATE TABLE app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            INSERT INTO app_settings (key, value) VALUES ('auto_create_note_on_launch', 'true');
            INSERT INTO app_settings (key, value) VALUES ('always_on_top', 'true');",
            kind: MigrationKind::Up,
        },
    ]
}
