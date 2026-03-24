use tauri::{
    image::Image,
    menu::{MenuBuilder, MenuItem},
    tray::TrayIconBuilder,
    App, Emitter, Manager,
};

pub fn setup(app: &App) {
    let icon = match Image::from_bytes(include_bytes!("../icons/icon.png")) {
        Ok(img) => img,
        Err(e) => {
            eprintln!("[tray] failed to load tray icon: {}", e);
            return;
        }
    };
    let show_hide = MenuItem::with_id(app, "show_hide", "Show/Hide", true, None::<&str>).unwrap();
    let new_note = MenuItem::with_id(app, "new_note", "New Note", true, None::<&str>).unwrap();
    let always_on_top = MenuItem::with_id(
        app,
        "always_on_top",
        "Toggle Always on Top",
        true,
        None::<&str>,
    )
    .unwrap();
    let auto_hide =
        MenuItem::with_id(app, "auto_hide", "Toggle Auto-hide", true, None::<&str>).unwrap();
    let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>).unwrap();

    let menu = MenuBuilder::new(app)
        .item(&show_hide)
        .item(&new_note)
        .separator()
        .item(&always_on_top)
        .item(&auto_hide)
        .separator()
        .item(&quit)
        .build()
        .unwrap();

    let result = TrayIconBuilder::new()
        .icon(icon)
        .tooltip("Antinote")
        .menu(&menu)
        .show_menu_on_left_click(true)
        .on_menu_event(|app, event| match event.id().as_ref() {
            "show_hide" => {
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
            "new_note" => {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.unminimize();
                    let _ = window.set_focus();
                }
                let _ = app.emit("tray-new-note", ());
            }
            "always_on_top" => {
                let _ = app.emit("tray-toggle-always-on-top", ());
            }
            "auto_hide" => {
                let _ = app.emit("tray-toggle-auto-hide", ());
            }
            "quit" => {
                let _ = app.emit("tray-quit", ());
                app.exit(0);
            }
            _ => {}
        })
        .build(app);

    match result {
        Ok(_) => eprintln!("[tray] system tray created successfully"),
        Err(e) => eprintln!("[tray] failed to create system tray: {}", e),
    }
}
