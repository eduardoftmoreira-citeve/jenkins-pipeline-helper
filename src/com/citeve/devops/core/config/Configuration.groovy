package com.citeve.devops.core.config

@Singleton(lazy=true)
class Configuration {
    
    final Map paths = [
        backupDir: "/home/emoreira/cicd-poc/backups",
        nginxLocations: "/home/users/cgomes/nginx/locations"
    ]
    
    final Map containers = [
        nginx: "nginx-proxy",
        jenkins: "jenkins-server"
    ]
    
    final Map ports = [
        startPort: 10000,
        maxPortRange: 1000,
        apiInternal: 3000,
        mongoInternal: 27017,
        redisInternal: 6379
    ]
    
    final Map health = [
        timeout: 60,
        interval: 5,
        expectedStatus: 200
    ]
    
    final Map logging = [
        info: "📣 INFO:",
        warning: "⚠️ WARNING:",
        fail: "❌ FAILED:",
        debug: "🪲 DEBUG:",
        success: "✅ SUCCESS:"
    ]
    
    final Map tags = [
        pilot: "piloto-cicd"
    ]
    
    final Map repos = [
        github: "https://api.github.com/repos/DEV-DTD-CITEVE/TEXPACT-WP2-PPS7/"
    ]
}