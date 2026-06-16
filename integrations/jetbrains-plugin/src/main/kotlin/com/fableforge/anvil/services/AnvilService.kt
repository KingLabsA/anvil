package com.fableforge.anvil.services

import com.intellij.openapi.components.Service
import com.intellij.openapi.project.Project
import com.fableforge.anvil.settings.AnvilSettingsState
import java.net.HttpURLConnection
import java.net.URL
import org.json.JSONObject

@Service(Service.Level.PROJECT)
class AnvilService(private val project: Project) {
    
    companion object {
        fun getInstance(project: Project): AnvilService {
            return project.getService(AnvilService::class.java)
        }
    }
    
    private val settings = AnvilSettingsState.getInstance()
    
    fun runTask(task: String): JSONObject? {
        val url = URL("${settings.serverUrl}/api/run")
        val connection = url.openConnection() as HttpURLConnection
        connection.requestMethod = "POST"
        connection.setRequestProperty("Content-Type", "application/json")
        connection.doOutput = true
        
        val jsonBody = JSONObject()
        jsonBody.put("task", task)
        jsonBody.put("model", settings.defaultModel)
        jsonBody.put("max_iterations", settings.maxIterations)
        
        connection.outputStream.use { os ->
            os.write(jsonBody.toString().toByteArray())
        }
        
        val response = connection.inputStream.bufferedReader().use { it.readText() }
        return JSONObject(response)
    }
    
    fun verifyCode(code: String, filePath: String, language: String): JSONObject? {
        val url = URL("${settings.serverUrl}/api/verify")
        val connection = url.openConnection() as HttpURLConnection
        connection.requestMethod = "POST"
        connection.setRequestProperty("Content-Type", "application/json")
        connection.doOutput = true
        
        val jsonBody = JSONObject()
        jsonBody.put("code", code)
        jsonBody.put("file_path", filePath)
        jsonBody.put("language", language)
        
        connection.outputStream.use { os ->
            os.write(jsonBody.toString().toByteArray())
        }
        
        val response = connection.inputStream.bufferedReader().use { it.readText() }
        return JSONObject(response)
    }
    
    fun explainCode(code: String): JSONObject? {
        val url = URL("${settings.serverUrl}/api/explain")
        val connection = url.openConnection() as HttpURLConnection
        connection.requestMethod = "POST"
        connection.setRequestProperty("Content-Type", "application/json")
        connection.doOutput = true
        
        val jsonBody = JSONObject()
        jsonBody.put("code", code)
        
        connection.outputStream.use { os ->
            os.write(jsonBody.toString().toByteArray())
        }
        
        val response = connection.inputStream.bufferedReader().use { it.readText() }
        return JSONObject(response)
    }
    
    fun refactorCode(code: String, suggestion: String): JSONObject? {
        val url = URL("${settings.serverUrl}/api/refactor")
        val connection = url.openConnection() as HttpURLConnection
        connection.requestMethod = "POST"
        connection.setRequestProperty("Content-Type", "application/json")
        connection.doOutput = true
        
        val jsonBody = JSONObject()
        jsonBody.put("code", code)
        jsonBody.put("suggestion", suggestion)
        
        connection.outputStream.use { os ->
            os.write(jsonBody.toString().toByteArray())
        }
        
        val response = connection.inputStream.bufferedReader().use { it.readText() }
        return JSONObject(response)
    }
    
    fun fixErrors(code: String, errors: List<JSONObject>): JSONObject? {
        val url = URL("${settings.serverUrl}/api/fix")
        val connection = url.openConnection() as HttpURLConnection
        connection.requestMethod = "POST"
        connection.setRequestProperty("Content-Type", "application/json")
        connection.doOutput = true
        
        val jsonBody = JSONObject()
        jsonBody.put("code", code)
        jsonBody.put("errors", errors)
        
        connection.outputStream.use { os ->
            os.write(jsonBody.toString().toByteArray())
        }
        
        val response = connection.inputStream.bufferedReader().use { it.readText() }
        return JSONObject(response)
    }
    
    fun generateTests(code: String, filePath: String, language: String): JSONObject? {
        val url = URL("${settings.serverUrl}/api/generate-tests")
        val connection = url.openConnection() as HttpURLConnection
        connection.requestMethod = "POST"
        connection.setRequestProperty("Content-Type", "application/json")
        connection.doOutput = true
        
        val jsonBody = JSONObject()
        jsonBody.put("code", code)
        jsonBody.put("file_path", filePath)
        jsonBody.put("language", language)
        
        connection.outputStream.use { os ->
            os.write(jsonBody.toString().toByteArray())
        }
        
        val response = connection.inputStream.bufferedReader().use { it.readText() }
        return JSONObject(response)
    }
}
