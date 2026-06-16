package com.fableforge.anvil.settings

import com.intellij.openapi.options.Configurable
import javax.swing.*
import java.awt.GridBagConstraints
import java.awt.GridBagLayout
import java.awt.Insets

class AnvilSettingsConfigurable : Configurable {
    
    private var settingsPanel: JPanel? = null
    private var serverUrlField: JTextField? = null
    private var defaultModelCombo: JComboBox<String>? = null
    private var maxIterationsSpinner: JSpinner? = null
    private var autoVerifyCheckbox: JCheckBox? = null
    private var themeCombo: JComboBox<String>? = null
    
    override fun getDisplayName(): String = "Anvil"
    
    override fun createComponent(): JComponent {
        val panel = JPanel(GridBagLayout())
        val gbc = GridBagConstraints()
        gbc.fill = GridBagConstraints.HORIZONTAL
        gbc.insets = Insets(5, 5, 5, 5)
        
        // Server URL
        gbc.gridx = 0
        gbc.gridy = 0
        gbc.weightx = 0.0
        panel.add(JLabel("Server URL:"), gbc)
        
        serverUrlField = JTextField()
        gbc.gridx = 1
        gbc.weightx = 1.0
        panel.add(serverUrlField, gbc)
        
        // Default Model
        gbc.gridx = 0
        gbc.gridy = 1
        gbc.weightx = 0.0
        panel.add(JLabel("Default Model:"), gbc)
        
        defaultModelCombo = JComboBox(arrayOf("local", "gpt-4o", "claude-3-5-sonnet"))
        gbc.gridx = 1
        gbc.weightx = 1.0
        panel.add(defaultModelCombo, gbc)
        
        // Max Iterations
        gbc.gridx = 0
        gbc.gridy = 2
        gbc.weightx = 0.0
        panel.add(JLabel("Max Iterations:"), gbc)
        
        maxIterationsSpinner = JSpinner(SpinnerNumberModel(20, 1, 100, 1))
        gbc.gridx = 1
        gbc.weightx = 1.0
        panel.add(maxIterationsSpinner, gbc)
        
        // Auto Verify
        gbc.gridx = 0
        gbc.gridy = 3
        gbc.gridwidth = 2
        autoVerifyCheckbox = JCheckBox("Automatically verify code after changes")
        panel.add(autoVerifyCheckbox, gbc)
        
        // Theme
        gbc.gridx = 0
        gbc.gridy = 4
        gbc.gridwidth = 1
        gbc.weightx = 0.0
        panel.add(JLabel("Theme:"), gbc)
        
        themeCombo = JComboBox(arrayOf("dark", "light"))
        gbc.gridx = 1
        gbc.weightx = 1.0
        panel.add(themeCombo, gbc)
        
        // Spacer
        gbc.gridx = 0
        gbc.gridy = 5
        gbc.gridwidth = 2
        gbc.weighty = 1.0
        panel.add(JPanel(), gbc)
        
        settingsPanel = panel
        return panel
    }
    
    override fun isModified(): Boolean {
        val settings = AnvilSettingsState.getInstance()
        return serverUrlField?.text != settings.serverUrl ||
               defaultModelCombo?.selectedItem != settings.defaultModel ||
               maxIterationsSpinner?.value != settings.maxIterations ||
               autoVerifyCheckbox?.isSelected != settings.autoVerify ||
               themeCombo?.selectedItem != settings.theme
    }
    
    override fun apply() {
        val settings = AnvilSettingsState.getInstance()
        settings.serverUrl = serverUrlField?.text ?: "http://localhost:8000"
        settings.defaultModel = defaultModelCombo?.selectedItem as? String ?: "local"
        settings.maxIterations = maxIterationsSpinner?.value as? Int ?: 20
        settings.autoVerify = autoVerifyCheckbox?.isSelected ?: true
        settings.theme = themeCombo?.selectedItem as? String ?: "dark"
    }
    
    override fun reset() {
        val settings = AnvilSettingsState.getInstance()
        serverUrlField?.text = settings.serverUrl
        defaultModelCombo?.selectedItem = settings.defaultModel
        maxIterationsSpinner?.value = settings.maxIterations
        autoVerifyCheckbox?.isSelected = settings.autoVerify
        themeCombo?.selectedItem = settings.theme
    }
    
    override fun disposeUIResources() {
        settingsPanel = null
        serverUrlField = null
        defaultModelCombo = null
        maxIterationsSpinner = null
        autoVerifyCheckbox = null
        themeCombo = null
    }
}
