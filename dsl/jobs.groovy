def projects = [
    'pps7': [
        repo: 'https://github.com/DEV-DTD-CITEVE/TEXPACT-WP2-PPS7.git',
    ]

    //Projetos podem ser adicionados aqui conforme necessário
    //'novoprojeto': [
    //   repo: 'https://github.com/DEV-DTD-CITEVE/novoprojeto.git',
    //],
]

projects.each { projectName, config ->
    multibranchPipelineJob("${projectName}") {
        displayName(projectName)
        description(config.description)
        
        branchSources {
            git {
                id("${projectName}-source")
                remote(config.repo)
                credentialsId('github-PAT')
            }
        }
        
        factory {
            workflowBranchProjectFactory {
                scriptPath('Jenkinsfile')
            }
        }
        
        triggers {
            periodicFolderTrigger {
                interval('5m')
            }
        }
        
        orphanedItemStrategy {
            discardOldItems {
                daysToKeep(7)
                numToKeep(10)
            }
        }
        
        //configure {
        //    it / sources / data / 'jenkinsfilePath'('Jenkinsfile')
        //}
    }
}

listView('All Projects') {
    description('All project pipelines')
    jobs {
        regex('/.*')
    }
    columns {
        status()
        weather()
        name()
        lastSuccess()
        lastFailure()
        lastDuration()
        buildButton()
    }
}