package com.fableforge.anvil.settings

import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.components.PersistentStateComponent
import com.intellij.openapi.components.State
import com.intellij.openapi.components.Storage
import com.intellij.util.xmlb.XmlSerializerUtil

@State(
    name = "com.fableforge.anvil.settings.AnvilSettingsState",
    storages = [Storage("AnvilSettings.xml")]
)
class AnvilSettingsState : PersistentStateComponent<AnvilSettingsState> {
    
    var serverUrl: String = "http://localhost:8000"
    var defaultModel: String = "local"
    var maxIterations: Int = 20
    var autoVerify: Boolean = true
    var theme: String = "dark"
    
    companion object {
        fun getInstance(): AnvilSettingsState {
            return ApplicationManager.getApplication().getService(AnvilSettingsState::class.java)
        }
    }
    
    override fun getState(): AnvilSettingsState {
        return this
    }
    
    override fun loadState(state: AnvilSettingsState) {
        XmlSerializerUtil.copyBean(state, this)
    }
}
