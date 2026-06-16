use tauri::Manager;
use std::process::{Command, Child};
use std::sync::Mutex;
use std::time::Duration;
use std::thread;

struct ServerState {
    child: Option<Child>,
}

#[tauri::command]
async fn check_server() -> Result<bool, String> {
    // Try to connect to the server
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(2))
        .build()
        .map_err(|e| e.to_string())?;
    
    match client.get("http://localhost:8000/health").send().await {
        Ok(resp) => Ok(resp.status().is_success()),
        Err(_) => Ok(false),
    }
}

#[tauri::command]
async fn start_server(app: tauri::AppHandle) -> Result<(), String> {
    // Check if server is already running
    if check_server().await.unwrap_or(false) {
        return Ok(());
    }

    // Find the anvil executable
    let anvil_path = which::which("anvil")
        .map_err(|_| "Anvil CLI not found. Please install with: pip install fableforge-anvil-agent[all]")?;

    // Start the server as a child process
    let child = Command::new(anvil_path)
        .args(&["serve", "--port", "8000"])
        .spawn()
        .map_err(|e| format!("Failed to start server: {}", e))?;

    // Store the child process
    app.state::<Mutex<ServerState>>()
        .lock()
        .unwrap()
        .child = Some(child);

    // Wait for server to be ready
    for _ in 0..30 {
        thread::sleep(Duration::from_millis(500));
        if check_server().await.unwrap_or(false) {
            return Ok(());
        }
    }

    Err("Server failed to start within 15 seconds".to_string())
}

fn main() {
    tauri::Builder::default()
        .manage(Mutex::new(ServerState { child: None }))
        .invoke_handler(tauri::generate_handler![check_server, start_server])
        .setup(|app| {
            let app_handle = app.handle();
            
            // Start server automatically on app launch
            tauri::async_runtime::spawn(async move {
                if let Err(e) = start_server(app_handle).await {
                    eprintln!("Failed to start server: {}", e);
                }
            });
            
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                // Kill the server when window closes
                if let Some(mut child) = window.app_handle()
                    .state::<Mutex<ServerState>>()
                    .lock()
                    .unwrap()
                    .child.take()
                {
                    let _ = child.kill();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
