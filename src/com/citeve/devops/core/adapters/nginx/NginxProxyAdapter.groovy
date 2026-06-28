package com.citeve.devops.core.adapters.nginx

import com.citeve.devops.core.model.Project
import com.citeve.devops.core.model.Component
import com.citeve.devops.core.ports.ProxyPort
import com.citeve.devops.core.config.Configuration

class NginxProxyAdapter implements ProxyPort {
    
    // ✅ Matches interface: 2 parameters
    void deployConfig(Project project, String branch) {
        def confName = "${Configuration.TAGS.pilot}-${project.name}-${branch}.conf"
        def configContent = buildNginxConfig(project, branch)
        
        writeFile file: confName, text: configContent
        
        sh """
            mv ${confName} ${Configuration.PATHS.nginxLocations}/
            if docker exec ${Configuration.CONTAINERS.nginx} nginx -t 2>/dev/null; then
                docker exec ${Configuration.CONTAINERS.nginx} nginx -s reload
            else
                rm ${Configuration.PATHS.nginxLocations}/${confName}
                exit 1
            fi
        """
    }
    
    // ✅ Matches interface: 2 parameters
    void removeConfig(Project project, String branch) {
        def confName = "${Configuration.TAGS.pilot}-${project.name}-${branch}.conf"
        sh """
            rm -f ${Configuration.PATHS.nginxLocations}/${confName}
            docker exec ${Configuration.CONTAINERS.nginx} nginx -s reload 2>/dev/null || true
        """
    }
    
    // ✅ Matches interface: 0 parameters
    void reloadProxy() {
        sh "docker exec ${Configuration.CONTAINERS.nginx} nginx -s reload 2>/dev/null || true"
    }
    
    private String buildNginxConfig(Project project, String branch) {
        def apiComponent = project.findComponent('api')
        def port = apiComponent?.port ?: Configuration.PORTS.apiInternal
        def containerName = "${project.name}-api-${branch}"
        def basePath = "/${Configuration.TAGS.pilot}/${project.name}/${branch}"
        
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