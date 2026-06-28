package com.citeve.devops.core.adapters.backup

import com.citeve.devops.core.model.Project
import com.citeve.devops.core.model.Component
import com.citeve.devops.core.ports.BackupPort
import com.citeve.devops.core.config.Configuration

class MongoBackupAdapter implements BackupPort {
    
    void createBackup(Project project, String backupDir) {
        def mongoComponent = project.findComponent('mongo')
        if (!mongoComponent) return
        
        def dbName = project.name.replaceAll('-', '_')
        def timestamp = new Date().format("yyyyMMdd_HHmmss")
        def backupFile = "${backupDir}/${project.name}/mongo_backup_${timestamp}.archive"
        def containerName = "${project.name}-mongo-${project.branch}"
        
        sh """
            mkdir -p ${backupDir}/${project.name}
            docker exec ${containerName} mongodump --db ${dbName} --archive > ${backupFile}
            find ${backupDir}/${project.name} -name "*.archive" -mtime +7 -delete
        """
    }
    
    void restoreBackup(Project project, String backupFile) {
        def containerName = "${project.name}-mongo-${project.branch}"
        sh """
            cat ${backupFile} | docker exec -i ${containerName} mongorestore --archive
        """
    }
    
    boolean isBackupSupported() {
        return true
    }
}