/*
 * GitHub Branch Source is used rather than the generic Git SCM source so Jenkins
 * discovers same-repository pull requests and populates CHANGE_ID/CHANGE_TARGET.
 * Fork pull requests are not discovered by this seed configuration.
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
                                strategyId(1)
                            }
                            // Discover pull requests from the same repository. This
                            // creates CHANGE_ID and CHANGE_TARGET for reviewPullRequest().
                            gitHubPullRequestDiscovery {
                                strategyId(1)
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
