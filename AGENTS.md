# TV Dash CI/CD instructions for agents

## Application profile

TV Dash is a public GitHub repository containing a Python 3.12 FastAPI backend
and a separately sideloaded Roku application. CI/CD deploys only the backend.

The standardized deployable image is:

```text
ghcr.io/kanedasec/tvdash-app:sha-<full-commit-sha>
```

The public origin is `https://tvdash.kanedasec.com.br`. Its dashboard root is
deliberately protected by HTTP Basic authentication and must return `401`
without credentials. `/healthz` is unauthenticated, contains no sensitive
data, and must return exactly `200` through Caddy for deployment readiness.

## Required architecture

```text
feature branch -> pull request
  |-> Standard CI (Python tests and workflow validation)
  `-> full-repository Semgrep, Gitleaks, and Trivy -> SGP Manager gate
protected merge -> main
  -> rebuild tests
  -> build and publish GHCR sha-<commit>
  -> ephemeral tag:github-deploy Tailscale node
  -> SSH as deployer
  -> forced deploy-tvdash command
  -> restricted sudo /usr/local/sbin/deploy-tvdash
  -> Docker Compose pull/up/health check
  -> Caddy -> authenticated public application
```

GitHub-hosted runners build and validate. The VPS only pulls and runs images.

## Trust boundaries that must not be weakened

1. Never deploy a pull request or an unprotected branch.
2. Keep external actions and workflows pinned to reviewed full commit SHAs.
3. Do not expose public SSH or add TCP/22 to the Netcup firewall.
4. Do not add `deployer` to the Docker group or grant general sudo.
5. Do not install a persistent general-purpose runner on the VPS.
6. Do not publish the container's port 8000 on the VPS.
7. Keep Caddy as the only public ingress through the external `proxy` network.
8. Do not build from `/opt/apps/tvdash`; production Compose uses the GHCR image.
9. Do not commit the VPS Compose definition, Telegram token, web password,
   Roku API key, Tailscale credentials, SSH private key, or SGP API key here.
10. Do not deploy `latest` or `dev`; deploy only `sha-<40 lowercase hex>`.
11. Do not put scanner suppressions in this application repository. Exceptions
    are reviewed centrally through SGP Manager/platform policy.
12. Preserve SQLite state at `/opt/data/tvdash/db/tvdash.db` across deployments.

Docker access and the root-owned deployment script are root-equivalent trust
boundaries. Application source and workflow inputs must never be able to choose
an arbitrary command, Compose path, service, image repository, or host path.

## Repository and platform responsibilities

This repository owns application source, tests, Dockerfile, and the two small
workflow callers in `.github/workflows/`.

`kanedasec/platform-workflows` owns reusable CI, full-repository scanners, GHCR
publishing, SGP policy evaluation, and ephemeral Tailscale/SSH deployment.
Every caller reference must use the same reviewed 40-character revision.

The public `compose.yml` is for notebook development only. The authoritative
runtime definition is root-controlled at `/opt/infra/tvdash/compose.yaml` on
the VPS. Runtime secrets remain in root-readable environment files there.

## Pipeline ordering

Pull requests run Standard CI and Security independently. Publishing and
deployment are skipped. A push to `main` follows one dependency graph:

```text
standard-ci -> containers -> deploy
```

Do not split deployment into an independent push workflow, because independent
workflows may run concurrently.

## GitHub configuration contract

The `security-policy` Environment provides only:

```text
SGP_MANAGER_API_KEY (secret)
```

The `development` Environment is restricted to `main` and provides:

```text
TS_OAUTH_CLIENT_ID       secret
TS_OAUTH_SECRET          secret
DEPLOY_SSH_PRIVATE_KEY   secret
DEPLOY_HOST              variable: 100.114.123.6
DEPLOY_USER              variable: deployer
DEPLOY_COMMAND           variable: deploy-tvdash
DEPLOY_URL               variable: https://tvdash.kanedasec.com.br
DEPLOY_KNOWN_HOSTS       variable: trusted pinned VPS host-key line
```

The repository variable `DEPLOY_ENABLED` is `false` only during initial VPS
bootstrap or an intentional deployment freeze. Normal operation requires
`DEPLOY_ENABLED=true`; changing it is a deployment-control decision.

The shared deployment identity deliberately reduces credential management but
increases blast radius. Server-side forced-command and sudo allowlists are the
compensating controls and must explicitly map `deploy-tvdash` to exactly
`/usr/local/sbin/deploy-tvdash`.

## VPS runtime contract

The production Compose service is named `tvdash` and uses:

```yaml
image: ghcr.io/kanedasec/tvdash-app:${IMAGE_TAG:?IMAGE_TAG must be set}
```

It retains the existing two environment files, bind-mounted database directory,
read-only filesystem, tmpfs, dropped capabilities, health check, and `proxy`
network. It has `expose: ["8000"]` and no `build:` or `ports:`.

`/opt/infra/tvdash/deployment.env` contains only:

```dotenv
IMAGE_TAG=sha-<full-commit-sha>
```

The root-owned deploy script must validate the tag, lock concurrent deploys,
pull only service `tvdash`, verify the OCI revision label matches the commit,
atomically update `deployment.env`, run `docker compose up -d --no-build`, wait
for health, and restore the previous tag if deployment fails.

## Required verification

Before declaring the integration complete, confirm:

- `python -m pytest -q tests` passes from `backend/`;
- Actionlint accepts both workflow files;
- no secrets are detected and every `uses:` is full-SHA pinned;
- the PR passes Standard CI, Semgrep, Gitleaks, Trivy, and SGP policy;
- GHCR publishes `tvdash-app:sha-<merge-commit>`;
- production Compose has no `build:` or `ports:` and resolves with `config --quiet`;
- `deployer` cannot run unrelated sudo commands and is not in `docker`;
- the deployed image revision, deployment tag, and merge commit match;
- the container is healthy, `/` returns 401 without credentials, and
  `/healthz` returns 200 through public HTTPS.
