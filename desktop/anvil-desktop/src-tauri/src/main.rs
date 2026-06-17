#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::Manager;
use std::process::{Command, Child};
use std::sync::Mutex;
use std::time::Duration;
use std::thread;

struct ServerState {
    child: Option<Child>,
}

fn check_server_sync() -> bool {
    Command::new("curl")
        .args(&["-s", "-f", "http://localhost:8000/health"])
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false)
}

#[tauri::command]
fn start_server(state: tauri::State<Mutex<ServerState>>) -> Result<(), String> {
    if check_server_sync() {
        return Ok(());
    }

    let anvil_path = which::which("anvil")
        .map_err(|_| "Anvil CLI not found. Install with: pip install fableforge-anvil-agent[all]")?;

    let child = Command::new(anvil_path)
        .args(&["serve", "--port", "8000"])
        .spawn()
        .map_err(|e| format!("Failed to start server: {}", e))?;

    state.lock().unwrap().child = Some(child);

    for _ in 0..30 {
        thread::sleep(Duration::from_millis(500));
        if check_server_sync() {
            return Ok(());
        }
    }

    Err("Server failed to start".to_string())
}

#[tauri::command]
fn get_models() -> Vec<String> {
    vec![
        "shellwhisperer".into(),
        "gpt-4o".into(),
        "claude-3.5-sonnet".into(),
        "gemini-2.0-flash".into(),
        "deepseek-coder".into(),
    ]
}

#[tauri::command]
fn get_tools() -> Vec<String> {
    vec![
        "read_file".into(),
        "write_file".into(),
        "http_request".into(),
        "git_status".into(),
    ]
}

fn main() {
    tauri::Builder::default()
        .manage(Mutex::new(ServerState { child: None }))
        .invoke_handler(tauri::generate_handler![
            start_server,
            get_models,
            get_tools,
        ])
        .setup(|app| {
            let state = app.state::<Mutex<ServerState>>();
            let _ = start_server(state.into());
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error running tauri app");
}
