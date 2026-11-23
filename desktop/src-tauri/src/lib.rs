//! CLPE Desktop qobig'i. UI — web ilovaning o'zi (web/dist), backend esa sozlanadigan CLPE server.
//!
//! Xavfsizlik: desktop ilova host tizimida hech qanday ixtiyoriy buyruq bajarmaydi.
//! VM boshqaruvi faqat server/Lab Agent orqali (spetsifikatsiya 5.3 va 9-bo'lim).

#[tauri::command]
fn platform_info() -> serde_json::Value {
    serde_json::json!({
        "os": std::env::consts::OS,
        "arch": std::env::consts::ARCH,
        "version": env!("CARGO_PKG_VERSION"),
    })
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![platform_info])
        .run(tauri::generate_context!())
        .expect("CLPE Desktop ishga tushmadi");
}
