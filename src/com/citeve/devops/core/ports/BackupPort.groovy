package com.citeve.devops.core.ports

import com.citeve.devops.core.model.Project

interface BackupPort {
    void createBackup(Project project, String backupDir)
    void restoreBackup(Project project, String backupFile)
    boolean isBackupSupported()
}