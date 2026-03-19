mod migrations;
mod shortcuts;
#[cfg(desktop)]
mod tray;

use tauri::Manager;
use tauri_plugin_sql::Builder as SqlBuilder;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(
            SqlBuilder::default()
                .add_migrations("sqlite:notes.db", migrations::get_migrations())
                .build(),
        )
        .setup(|app| {
            #[cfg(desktop)]
            {
                shortcuts::setup(app);
                tray::setup(app);

                if let Some(window) = app.get_webview_window("main") {
                    let icon =
                        tauri::image::Image::from_bytes(include_bytes!("../icons/icon.png"))?;
                    let _ = window.set_icon(icon);
                }
            }

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
