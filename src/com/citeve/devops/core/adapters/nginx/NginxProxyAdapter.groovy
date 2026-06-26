package com.citeve.devops.core.adapters.nginx

import com.citeve.devops.core.model.Project
import com.citeve.devops.core.model.Component
import com.citeve.devops.core.ports.ProxyPort
import com.citeve.devops.core.config.Configuration

class NginxProxyAdapter implements ProxyPort {
    
    void deployConfig(Project project, String branch, Configuration config) {
        def confName = "${config.tags.pilot}-${project.name}-${branch}.conf"
        def configContent = buildNginxConfig(project, branch, config)
        
        writeFile file: confName, text: configContent
        
        sh """
            mv ${confName} ${config.paths.nginxLocations}/
            if docker exec ${config.containers.nginx} nginx -t 2>/dev/null; then
                docker exec ${config.containers.nginx} nginx -s reload
            else
                rm ${config.paths.nginxLocations}/${confName}
                exit 1
            fi
        """
    }
    
    void removeConfig(Project project, String branch, Configuration config) {
        def confName = "${config.tags.pilot}-${project.name}-${branch}.conf"
        sh """
            rm -f ${config.paths.nginxLocations}/${confName}
            docker exec ${config.containers.nginx} nginx -s reload 2>/dev/null || true
        """
    }
    
    void reloadProxy(Configuration config) {
        sh "docker exec ${config.containers.nginx} nginx -s reload 2>/dev/null || true"
    }
    
    private String buildNginxConfig(Project project, String branch, Configuration config) {
        def apiComponent = project.findComponent('api')
        def port = apiComponent?.port ?: config.ports.apiInternal
        def containerName = "${project.name}-api-${branch}"
        def basePath = "/${config.tags.pilot}/${project.name}/${branch}"
        
        return """
            location ^~ ${basePath}/ {
                proxy_pass http://${containerName}:${port}/;
                proxy_set_header Host \$host;
                proxy_set_header X-Real-IP \$remote_addr;
                proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
                proxy_set_header X-Forwarded-Proto \$scheme;
                proxy_set_header X-Forwarded-Prefix ${basePath};
            }
        """
    }
}