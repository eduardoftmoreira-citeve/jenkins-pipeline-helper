package com.citeve.devops.core.ports

import com.citeve.devops.core.model.Project

interface ProxyPort {
    void deployConfig(Project project, String branch)
    void removeConfig(Project project, String branch)
    void reloadProxy()
}