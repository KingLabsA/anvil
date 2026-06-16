package com.fableforge.anvil.actions

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.actionSystem.CommonDataKeys
import com.intellij.openapi.ui.Messages
import com.fableforge.anvil.services.AnvilService

class RunTaskAction : AnAction() {
    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        
        val task = Messages.showInputDialog(
            project,
            "Enter task for Anvil:",
            "Run Task",
            null
        ) ?: return
        
        val service = AnvilService.getInstance(project)
        service.runTask(task)
    }

    override fun update(e: AnActionEvent) {
        e.presentation.isEnabledAndVisible = e.project != null
    }
}
