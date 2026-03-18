use tauri::{App, Manager};
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};

pub fn setup(app: &App) {
    let shortcut = Shortcut::new(Some(Modifiers::ALT), Code::KeyA);

    let result = app.handle().plugin(
        tauri_plugin_global_shortcut::Builder::new()
            .with_handler(move |app, s, event| {
                if s == &shortcut && event.state() == ShortcutState::Pressed {
                    if let Some(window) = app.get_webview_window("main") {
                        if window.is_visible().unwrap_or(false) {
                            let _ = window.hide();
                        } else {
                            let _ = window.show();
                            let _ = window.unminimize();
                            let _ = window.set_focus();
                        }
                    }
                }
            })
            .build(),
    );

    match result {
        Ok(_) => {
            if let Err(e) = app.global_shortcut().register(shortcut) {
                eprintln!("Failed to register global shortcut Alt+A: {}", e);
            }
        }
        Err(e) => {
            eprintln!("Failed to initialize global shortcut plugin: {}", e);
        }
    }
}
