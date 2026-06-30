# Ollama pull-request reviews

`reviewPullRequest()` is a Jenkins shared-library step separate from deployment. It is intended for multibranch pull-request builds. The code diff is sent only to the platform-configured local Ollama endpoint, then one marked GitHub pull-request timeline comment is created or updated.

## Pull-request discovery

The supplied `dsl/jobs.groovy` uses Jenkins **GitHub Branch Source** with same-repository pull-request discovery. This is required because a generic Git multibranch source normally does not expose `CHANGE_ID` and `CHANGE_TARGET`. Re-run the seed job after merging this helper branch. Fork pull requests are intentionally not discovered by the provided Job DSL.

## Pipeline usage

```groovy
@Library('jenkins-pipeline-helper') _

pipeline {
  agent any

  stages {
    stage('AI PR review') {
      when { changeRequest() }
      steps {
        reviewPullRequest(githubTokenCredentialId: 'github-pr-comment-token')
      }
    }

    stage('Deploy') {
      when { not { changeRequest() } }
      steps {
        deploy()
      }
    }
  }
}
```

The Jenkins credential must be **Secret Text** containing a GitHub token. The default variable name is `GITHUB_TOKEN`; do not commit it to a repository or platform config. The token needs permission to create and update pull-request timeline comments.

For the first test, generate the review without publishing it:

```groovy
reviewPullRequest(dryRun: true)
```

## Configuration

The shared library owns the configuration in `resources/platform-config.yaml`:

```yaml
review:
  enabled: true
  fail_on_error: false
  ollama:
    generate_url: http://192.168.54.202:11434/api/generate
    model: qwen2.5-coder:7b
    timeout_seconds: 120
  max_diff_characters: 120000
  max_files: 60
  github:
    api_url: https://api.github.com
    token_env: GITHUB_TOKEN
    comment_marker: '<!-- cicd-ollama-review -->'
```

`max_diff_characters` and `max_files` bound the review prompt. When limits are reached, the published comment says that its scope was limited. `fail_on_error: false` means an unavailable Ollama endpoint, missing credential, GitHub failure, or Git fetch failure causes a visible skip rather than a failed PR build.

## Safety controls

- The diff is treated as untrusted input and is explicitly framed that way in the model prompt.
- Git fetch uses the existing Jenkins `origin` remote, so the GitHub token is not placed in command arguments.
- Fork pull requests are skipped by default. Do not enable `allowForks: true` until your Jenkins PR trust model has been audited.
- Repeated builds update one comment identified by the configured hidden marker instead of adding comment clutter.
- `reviewPullRequest()` does not deploy containers, alter state, or invoke maintenance commands.
