/*
 * GitHub Branch Source discovers ordinary repository branches. Pull requests are
 * deliberately not discovery targets: a branch build asks GitHub whether its
 * source branch currently has an open same-repository pull request.
 */
def projects = [
    'pps7': [
        owner: 'DEV-DTD-CITEVE',
        repository: 'TEXPACT-WP2-PPS7',
        checkoutCredentialsId: 'github-PAT',
    ],

    // Add projects in the same form:
    // 'another-project': [
    //     owner: 'DEV-DTD-CITEVE',
    //     repository: 'another-project',
    //     checkoutCredentialsId: 'github-PAT',
    // ],
]

def allowedBranchRegex = '^(main|master|prod|production|stage|staging|dev|develop|development|release/.+|bugfix/.+)$'

projects.each { projectName, config ->
    multibranchPipelineJob(projectName) {
        displayName(projectName)
        description(config.description ?: "${config.owner}/${config.repository}")

        branchSources {
            branchSource {
                source {
                    github {
                        id("${projectName}-source")
                        credentialsId(config.checkoutCredentialsId)
                        configuredByUrl(true)
                        // The GitHub Branch Source plugin expects the organization URL
                        // without a .git suffix.
                        repositoryUrl("https://github.com/${config.owner}")
                        repoOwner(config.owner)
                        repository(config.repository)
                        traits {
                            gitHubBranchDiscovery {
                                strategyId(3)
                            }
                            headRegexFilter {
                                regex(allowedBranchRegex)
                            }
                        }
                    }
                }
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
    }
}

listView('Deployments') {
    description('All project pipelines')
    jobs {
        regex('.*')
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
