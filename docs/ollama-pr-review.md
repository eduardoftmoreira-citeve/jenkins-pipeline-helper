# Ollama pull-request reviews from normal branch builds

`reviewPullRequest()` is a Jenkins shared-library step separate from deployment. It runs during an ordinary multibranch **branch build**, asks GitHub whether that branch has exactly one open same-repository pull request, then reviews the change and creates or updates one marked GitHub comment.

```text
Branch build for feature/login
  → GitHub: is there an open PR whose head is <owner>:feature/login?
  → no: print a skipped message and succeed
  → yes: fetch the PR base branch, produce a bounded diff, call Ollama, upsert one PR comment
```

## Jenkins source configuration

The supplied `dsl/jobs.groovy` uses Jenkins **GitHub Branch Source** with branch discovery only. It deliberately does **not** enable `gitHubPullRequestDiscovery`, so Jenkins does not make separate `PR-42` jobs.

After updating the shared-library branch:

1. Run the seed job.
2. Re-index the multibranch job.
3. Remove stale PR jobs if Jenkins does not prune them automatically.

## Application Jenkinsfile

Call the shared-library step from a normal stage. Developers do not provide a token, PR number, target branch, or credential ID.

```groovy
stage('Ollama review') {
    steps {
        reviewPullRequest()
    }
}
```

To generate a review without posting it to GitHub:

```groovy
reviewPullRequest(dryRun: true)
```

A dry run still needs the GitHub credential because the helper must first look up whether an open PR exists for the current branch.

## GitHub credential

The helper always binds the existing Jenkins credential:

```text
ID: github-PAT
Kind: Username with password
Username: GitHub user or bot username
Password: classic GitHub PAT
```

The password is temporarily exposed as `GITHUB_TOKEN`. The same credential can remain configured for Git checkout. The PAT needs access to read pull requests and create/update PR timeline comments. For private repositories using a classic token, that normally means the `repo` scope.

## What GitHub lookup means

The helper asks GitHub for open pull requests using the source branch as the `head` filter. The base branch comes from GitHub's matching PR, not Jenkins variables. This avoids reliance on `CHANGE_ID` or `CHANGE_TARGET`.

| Situation | Result |
| --- | --- |
| Branch has no open PR | Review step succeeds and reports a skip. Ollama is not called. |
| Branch has one open same-repository PR | Review is generated and the marker-tagged comment is created/updated. |
| Branch has multiple open PRs | Review is skipped with a clear message; the helper will not guess the target PR. |
| Branch is pushed after a PR opens | The normal branch build refreshes the review. |
| A PR opens without a push | No review runs until the branch is built again. Trigger a branch build manually or add a webhook policy later. |

Fork PRs are outside this branch-only model. The Job DSL does not create fork PR jobs, and the lookup only considers PRs whose source branch belongs to the same GitHub owner as the repository.

## Configuration

The shared library owns review settings in `resources/platform-config.yaml`:

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

`max_diff_characters` and `max_files` bound the review prompt. When limits are reached, the published comment says that its scope was limited. `fail_on_error: false` means an unavailable Ollama endpoint, a missing token, GitHub failure, or Git fetch failure produces a visible skipped review rather than failing the branch build.

## Safety controls

- The diff is treated as untrusted input and is explicitly framed that way in the model prompt.
- Git fetch uses the existing Jenkins `origin` remote, so the GitHub token is not placed in Git command arguments or logs.
- Repeated builds update one comment identified by the configured hidden marker instead of adding comment clutter.
- `reviewPullRequest()` does not deploy containers, alter state, or invoke maintenance commands.
