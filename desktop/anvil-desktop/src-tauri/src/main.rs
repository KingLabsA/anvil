#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::Manager;
use std::process::{Command, Child};
use std::sync::Mutex;
use std::time::Duration;
use std::thread;
use tauri_plugin_updater::UpdaterExt;

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

#[tauri::command]
async fn check_for_updates(app: tauri::AppHandle) -> Result<Option<String>, String> {
    let updater = app.updater().map_err(|e| e.to_string())?;
    
    match updater.check().await {
        Ok(Some(update)) => {
            // Update available
            Ok(Some(format!(
                "Version {} is available! Current: {}",
                update.version,
                env!("CARGO_PKG_VERSION")
            )))
        }
        Ok(None) => Ok(None),
        Err(e) => Err(e.to_string()),
    }
}

#[tauri::command]
async fn install_update(app: tauri::AppHandle) -> Result<(), String> {
    let updater = app.updater().map_err(|e| e.to_string())?;
    
    if let Some(update) = updater.check().await.map_err(|e| e.to_string())? {
        let progress = |current: usize, total: usize| {
            println!("Downloading: {current}/{total}");
        };
        
        update
            .download(progress)
            .await
            .map_err(|e| e.to_string())?;
        
        update.install().map_err(|e| e.to_string())?;
        
        // Restart the app
        tauri::process::relaunch(app).map_err(|e| e.to_string())?;
    }
    
    Ok(())
}

#[tauri::command]
async fn get_model_providers() -> Result<Vec<String>, String> {
    // Return available model providers
    Ok(vec![
        "local".to_string(),
        "openai".to_string(),
        "anthropic".to_string(),
        "gemini".to_string(),
        "bedrock".to_string(),
        "azure".to_string(),
        "deepseek".to_string(),
        "groq".to_string(),
        "mistral".to_string(),
        "cerebras".to_string(),
        "openrouter".to_string(),
        "copilot".to_string(),
        "vertex".to_string(),
        "huggingface".to_string(),
    ])
}

#[tauri::command]
async fn get_mcp_tools() -> Result<Vec<String>, String> {
    // Return available MCP tools
    Ok(vec![
        "read_file".to_string(),
        "write_file".to_string(),
        "http_request".to_string(),
        "git_status".to_string(),
        "git_diff".to_string(),
        "query_database".to_string(),
        "send_slack_message".to_string(),
        "create_github_issue".to_string(),
        "create_github_pr".to_string(),
    ])
}

#[tauri::command]
async fn create_share_link(session_id: String) -> Result<String, String> {
    // Create a shareable link for remote access
    Ok(format!("https://anvil.fableforge.ai/share/{}", session_id))
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(Mutex::new(ServerState { child: None }))
        .invoke_handler(tauri::generate_handler![
            check_server,
            start_server,
            check_for_updates,
            install_update,
            get_model_providers,
            get_mcp_tools,
            create_share_link
        ])
        .setup(|app| {
            let app_handle = app.handle();
            
            // Start server automatically on app launch
            tauri::async_runtime::spawn(async move {
                if let Err(e) = start_server(app_handle.clone()).await {
                    eprintln!("Failed to start server: {}", e);
                }
                
                // Check for updates after server starts
                thread::sleep(Duration::from_secs(5));
                if let Ok(Some(msg)) = check_for_updates(app_handle).await {
                    println!("{}", msg);
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
