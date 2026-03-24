// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    // WebKitGTK spawns multiple threads internally, which can race with Xlib
    // on X11, causing an `xcb_xlib_threads_sequence_lost` assertion crash.
    // Calling XInitThreads() before any GTK/Xlib usage enables Xlib's internal
    // locking so concurrent threads can safely make X11 requests.
    #[cfg(target_os = "linux")]
    unsafe {
        x11::xlib::XInitThreads();
    }

    antinote_linux_lib::run()
}
