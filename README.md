# Jenkins Pipeline Helper

A provider-based Jenkins shared library for deploying Dockerized applications to one Docker host. The active implementation is contained in this repository; application repositories provide a Dockerfile and one `app-config.yaml`.

## Entry points

```text
Application Jenkinsfile
  ├─ deploy()
  ├─ cleanupOrphans()
  ├─ reviewPullRequest()
  └─ maintenance(operation: 'backup' | 'restore', ...)
        ↓
Shared-library Groovy copies the Python engine and active platform config
        ↓
resources/python/deploy.py
        ↓
DeploymentEngine → provider registry → Docker / Nginx / state
```

The active platform configuration is committed at:

```text
resources/platform-config.yaml
```

`deploy()`, `cleanupOrphans()`, `reviewPullRequest()` and `maintenance()` copy it into `.jenkins-deploy/platform-config.yaml` automatically. Application repositories do **not** need a platform config. An exceptional agent-visible override remains available through `platformConfig: '/path/to/file.yaml'`.

## Groovy API

| Shared-library variable | Purpose |
| --- | --- |
| `deploy()` | Build and deploy the current application's supported branch. |
| `cleanupOrphans()` | Scheduled removal of feature/bugfix environments whose remote branches disappeared. |
| `reviewPullRequest()` | Generate or update one Ollama-generated comment on the current same-repository pull request. |
| `maintenance(operation: 'backup', branch: 'main')` | Run backup for every deployed resource whose provider supports it and has enabled policy. |
| `maintenance(operation: 'restore', branch: 'main', archive: '...', confirmEnvironment: 'prod')` | Destructive provider-neutral restore of the resource recorded in the archive manifest. |

Jenkins has no Mongo-specific entrypoints. It only asks the engine to perform a maintenance operation. The engine reads deployment state, selects the provider recorded for each resource, and invokes only providers that advertise the requested capability.

Examples:

```groovy
@Library('jenkins-pipeline-helper') _

deploy()
```

```groovy
// Scheduled production backup job.
maintenance(operation: 'backup', branch: 'main')
```

```groovy
// Normal branch-build stage. It skips when BRANCH_NAME has no open
// same-repository pull request. github-PAT is bound internally.
reviewPullRequest()
```

```groovy
// First-run diagnostic: generate the review but do not post to GitHub.
reviewPullRequest(dryRun: true)
```

```groovy
// Manual, destructive restore job. Never schedule this.
maintenance(
  operation: 'restore',
  branch: 'main',
  archive: '/home/users/cicd/backups/mongo/pps7-api/prod/mongo/20260630T021500Z.archive.gz',
  confirmEnvironment: 'prod'
)
```

Deployments print timestamped Python progress lines in Jenkins, for example:

```text
[deploy 14:08:31] Ensuring Docker network cicd-pps7-api-staging
[deploy 14:08:36] Creating service container cicd-pps7-api-api-staging
[deploy 14:08:41] App is live at: https://dev.citeve.pt/piloto-cicd/pps7-api/staging/api/
```

At the end, Jenkins prints a deployment summary with the branch, environment,
network, runtime containers and each routed app URL.

## Branch environments

| Branch | Environment | MongoDB | Redis/network |
| --- | --- | --- | --- |
| `main`, `master`, `prod`, `production` | `prod` | Dedicated container/database | Dedicated Redis and network |
| `dev`, `develop`, `development` | `dev` | Shared non-prod Mongo container, environment database | Dedicated Redis and network |
| `stage`, `staging` | `staging` | Shared non-prod Mongo container, environment database | Dedicated Redis and network |
| `feature/*` | `feature-…-<hash>` | Shared non-prod Mongo container, environment database | Dedicated Redis and network |
| `bugfix/*` | `bugfix-…-<hash>` | Shared non-prod Mongo container, environment database | Dedicated Redis and network |

The static branch aliases resolve to one canonical environment name. `refs/heads/` and `origin/` prefixes are normalized before resolution.

## Application configuration

Every application provides exactly one `app-config.yaml`. There are no environment overlays and no app-level authentication switches.

```yaml
project_name: pps7-api

infrastructure:
  mongo:
    type: mongo
    version: "8"
  redis:
    type: redis
    version: "7"

services:
  api:
    type: node
    port: 3000
    dockerfile: Dockerfile
    build_context: .
    depends_on: [mongo, redis]
    env:
      NODE_ENV: development
      PORT: "3000"
    health_check:
      path: /health
      status_code: 200
      timeout: 60
    route:
      enabled: true
      inject_base_path: false
```

The Node provider injects `MONGO_URI`, `MONGO_DB_NAME`, `REDIS_URL` and `REDIS_URI`. `BASE_PATH` is injected only when `route.inject_base_path: true`.

## Pull-request review with Ollama

`reviewPullRequest()` is separate from `deploy()`. It runs in an ordinary Jenkins multibranch **branch build**, reads `BRANCH_NAME`, and asks GitHub whether the branch has exactly one open same-repository pull request. When none exists, it prints a skipped message and succeeds without calling Ollama. When exactly one exists, GitHub supplies its base branch; the helper fetches that branch using the existing `origin` remote, collects a bounded diff, sends it to the platform-configured Ollama `POST /api/generate` endpoint, and creates or updates one GitHub pull-request timeline comment. Repeated branch builds update the marked comment instead of adding a comment per build.

The supplied `dsl/jobs.groovy` uses **GitHub Branch Source** with branch discovery only, filtered to production, staging, development, `release/*` and `bugfix/*` branches. It deliberately does **not** enable `gitHubPullRequestDiscovery`, so Jenkins does not create separate PR jobs or rely on `CHANGE_ID`/`CHANGE_TARGET`. Re-run the seed job and re-index multibranch jobs after applying this branch.

The shared library binds the password from the existing Jenkins **Username with password** credential `github-PAT` as `GITHUB_TOKEN`. Developers call only `reviewPullRequest()` or `reviewPullRequest(dryRun: true)`; they do not provide token IDs, PR numbers, or target branches. A dry run still binds the credential because GitHub must be queried to determine whether an open PR exists. The classic PAT needs access to read pull requests and create/update PR timeline comments, normally `repo` scope for private repositories.

If a branch has multiple open same-repository PRs, the helper skips the review rather than guessing a target. Fork pull requests are outside this branch-only setup. A PR that is opened without a subsequent push is reviewed when the branch is next built; trigger that build manually until you add a webhook policy for PR-open events.

The active platform config contains the Ollama endpoint, model, token environment-variable name, bounds and non-blocking policy. No token is committed. The committed `fail_on_error: false` policy means unreachable Ollama, a missing token, or a GitHub API error is reported as a skipped review rather than failing the branch pipeline. Change it to `true` only after the service is proven reliable and you intentionally want reviews to be required.

## Providers and maintenance

| Provider | Deploy responsibility | Maintenance capability today |
| --- | --- | --- |
| `MongoProvider` | Mongo image/container, per-environment databases and URI | backup, verified backup restore, restore |
| `RedisProvider` | One Redis container and volume per environment | none |
| `NodeProvider` | Docker image build/run, dependency variables, health check | none |
| `NginxRouter` | Location files and route names | none |

Provider capabilities are declared in the provider itself. Adding PostgreSQL later means implementing a `PostgresProvider`, registering it, and adding a `backups.providers.postgres` policy only if it supports backups. No Groovy files or Jenkinsfile API need to be added.

## Platform configuration and backups

The committed `resources/platform-config.yaml` contains platform-level paths and provider-specific backup policy:

```yaml
backups:
  providers:
    mongo:
      root_dir: /home/users/cicd/backups/mongo
      policies:
        production: ...
        staging: ...
```

This is intentionally provider-specific because storage location and retention are provider behavior. The **orchestrator** is provider-neutral.

Production Mongo archives are compressed, checksummed and restore-tested in a disposable Mongo container. Retention is 14 daily, 8 weekly and 12 monthly restore points. Staging archives are checksummed, retained for 7 daily and 2 weekly points, and do not run a restore test by default. All archives remain local to the Nexus server, so this is recovery support rather than off-site disaster recovery.

A backup manifest records `provider`, `resource`, project and environment. Restore uses that manifest to dispatch to the right provider and rejects archives outside that provider's configured backup root.

## Authentication and topology

MongoDB and Redis intentionally run without authentication in this startup-phase helper. Neither provider publishes a host port. Isolation comes from one Docker network per environment, per-environment Mongo databases, and a dedicated Redis container per environment. This is not access control for manually connected containers; reintroduce authentication before exposing infrastructure outside the private Docker model.

The active platform config uses the existing Nginx locations directory:

```text
/home/users/cgomes/nginx/locations
```

It also uses `nginx.public_url` to print full application links in Jenkins:

```text
https://dev.citeve.pt
```

These host paths must be writable and visible inside the Docker-capable Jenkins build agent:

```text
/home/users/cicd
/home/users/cgomes/nginx/locations
/var/run/docker.sock
```

`/home/users/cicd` contains `deployment-state/` and `backups/`. It must be mounted into the actual Docker-capable Jenkins **agent**, not only the Jenkins controller.

## Orphan cleanup

`cleanupOrphans()` uses `git ls-remote --heads`, compares live remote branch names with state, and removes only orphaned `feature/*` and `bugfix/*` environments. It removes application containers and Nginx routes, the dedicated Redis container/volume, Mongo's environment database, the network and state file. `dev`, `staging` and `prod` are never cleanup candidates.

## Tests

```bash
PYTHONPATH=resources/python python3 -m unittest discover -s tests -v
```

The tests are logic-only. They do not contact Docker, Jenkins, MongoDB, Redis, Nginx, Ollama or GitHub.

## First migration

1. Keep the existing helper on its legacy branch and place this repository on the replacement branch.
2. Add the single `app-config.yaml` to the PPS7 test application.
3. Ensure the Docker-capable agent can access Docker plus the Nginx, state and backup paths.
4. Validate `develop`, one `feature/*` branch, `staging`, then `main`.
5. Run a staging backup and manual restore in a planned window.
6. Schedule production/staging `maintenance(operation: 'backup', ...)` and `cleanupOrphans()` only after that validation.
