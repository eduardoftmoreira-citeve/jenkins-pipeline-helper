package com.citeve.devops.core.config

class Configuration {
    static final Map PATHS = [
        backupDir: "/home/emoreira/cicd-poc/backups",
        nginxLocations: "/home/users/cgomes/nginx/locations"
    ]
    
    static final Map CONTAINERS = [
        nginx: "nginx-proxy",
        jenkins: "jenkins-server"
    ]
    
    static final Map PORTS = [
        startPort: 10000,
        maxPortRange: 1000,
        apiInternal: 3000,
        mongoInternal: 27017,
        redisInternal: 6379
    ]
    
    static final Map HEALTH = [
        timeout: 60,
        interval: 5,
        expectedStatus: 200
    ]
    
    static final Map LOGGING = [
        info: "📣 INFO:",
        warning: "⚠️ WARNING:",
        fail: "❌ FAILED:",
        debug: "🪲 DEBUG:",
        success: "✅ SUCCESS:"
    ]
    
    static final Map TAGS = [
        pilot: "piloto-cicd"
    ]
    
    static final Map REPOS = [
        github: "https://api.github.com/repos/DEV-DTD-CITEVE/TEXPACT-WP2-PPS7/"
    ]
}