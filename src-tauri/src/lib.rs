mod migrations;

use tauri_plugin_sql::Builder as SqlBuilder;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(
            SqlBuilder::default()
                .add_migrations("sqlite:notes.db", migrations::get_migrations())
                .build(),
        )
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
