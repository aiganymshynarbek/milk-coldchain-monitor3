# Assignment 5 – running the CI/CD pipeline yourself

Everything below runs on your own computer. Total time: about 30–40 minutes,
most of it waiting for downloads the first time.

## Option A – nothing installed: GitHub Codespaces (recommended for a small laptop)

A Codespace is a Linux computer in GitHub's cloud that opens in the browser.
Docker is already inside it (see `.devcontainer/devcontainer.json`). Personal
GitHub accounts get 120 core-hours per month free (a 2-core Codespace uses
2 per hour, so about 60 hours), and no payment card is needed.

1. Put the project on GitHub (step 1 below) – this can also be done in the
   browser with "Add file → Upload files".
2. On the repository page: **Code → Codespaces → Create codespace on main**.
   Wait 2–3 minutes until VS Code opens in the browser.
3. In its terminal (bottom panel) run:
   ```bash
   export REPO_URL=https://github.com/$GITHUB_REPOSITORY.git
   docker compose -f docker-compose.jenkins.yml up -d --build
   ```
4. Open the **Ports** tab, find port **8080 (Jenkins)** and click the globe
   icon. Log in with **admin / admin** and continue with step 4 below.
   The deployed API is port **8000** in the same tab.
5. When finished, stop the Codespace (Codespaces list → … → Stop) so it does
   not use your free hours.

## Option B – on your own computer

## 0. What you need

| Tool | Why | Check |
|---|---|---|
| Docker Desktop (Windows/macOS) or Docker Engine (Linux) | builds and runs all containers, including Jenkins | `docker version` |
| Git | sends the project to GitHub | `git --version` |
| A GitHub account | hosts the repository Jenkins reads | – |
| (optional) Docker Hub account | for the "push image" stage | – |
| (optional) Minikube + kubectl | for the Kubernetes deployment bonus | `minikube version` |

## 1. Put the project on GitHub

```bash
cd milk-coldchain-monitor
git remote add origin https://github.com/<your-username>/milk-coldchain-monitor.git
git push -u origin main --tags
```
The repository must be **public** (Jenkins then needs no password to read it).

## 2. Check the Docker image by hand (optional but useful)

```bash
docker build --target test -t coldchain-monitor-test .
docker run --rm coldchain-monitor-test          # runs the unit tests, last line: "... passed"
docker build --target runtime -t coldchain-monitor .
docker run --rm -p 8000:8000 coldchain-monitor   # then open http://localhost:8000/health
```

## 3. Start Jenkins

```bash
# macOS / Linux
export REPO_URL=https://github.com/<your-username>/milk-coldchain-monitor.git
# Windows PowerShell
$env:REPO_URL="https://github.com/<your-username>/milk-coldchain-monitor.git"

docker compose -f docker-compose.jenkins.yml up -d --build
```
The first start downloads Jenkins and its plugins (5–10 minutes). Then open
**http://localhost:8080** and log in with **admin / admin**.

The job **coldchain-monitor** already exists – it was created by the
configuration file `jenkins/casc.yaml` (Configuration as Code), so nothing has
to be clicked together by hand.

## 4. Run the pipeline

1. Open the job → **Build with Parameters** → **Build**.
   (The first run only shows "Build Now"; after it, the parameters appear.)
2. Watch the stages: *Checkout → Unit tests → Build image → Smoke test →
   Push to Docker Hub (skipped unless enabled) → Deploy to staging*.
3. After a green run, open **http://localhost:8000/health** and
   **http://localhost:8000/forecast?hours=3** – this is the deployed service.

## 5. Show "tests on every commit"

Make any small change (for example a line in `README.md`), then
```bash
git commit -am "docs: trigger CI" && git push
```
Within about 2 minutes Jenkins notices the new commit (SCM polling) and starts
build #2 by itself. Its page says *"Started by an SCM change"*.

## 6. (Optional) Push to Docker Hub

1. Docker Hub → Account settings → **Personal access tokens** → create a token.
2. Jenkins → Manage Jenkins → Credentials → (global) → **Add credentials**:
   kind *Username with password*, ID **dockerhub**, username = Docker Hub
   login, password = the token.
3. Build with parameters: tick **PUSH_IMAGE**, set **DOCKERHUB_REPO** to
   `<dockerhub-user>/coldchain-monitor`.

## 7. (Optional, bonus) Deploy to Kubernetes with Minikube

```bash
minikube start
minikube image load coldchain-monitor:latest     # the image Jenkins built
kubectl apply -f k8s/
kubectl rollout status deployment/coldchain-monitor
kubectl get pods
minikube service coldchain-monitor --url         # open <url>/health
```

## 8. Screenshots to take for the report

1. Jenkins dashboard with the job and its weather icon.
2. The job page with the **Stage View** (all stages green).
3. The console output of a build (the unit-test summary line).
4. The **Test Result** page (73 tests, 0 failures).
5. A build "Started by an SCM change" (proof of the commit trigger).
6. `docker image ls coldchain-monitor` in a terminal.
7. The browser at `http://localhost:8000/forecast?hours=3`.
8. (optional) Docker Hub repository page; `kubectl get pods`.

## Troubleshooting

| Problem | Fix |
|---|---|
| `permission denied ... docker.sock` in a build | the compose file runs Jenkins as root; recreate it with `docker compose -f docker-compose.jenkins.yml up -d --force-recreate` |
| Port 8080 or 8000 already used | change the left side of the port mapping, e.g. `"8081:8080"` |
| The job is not there | check `docker logs jenkins` for errors from the configuration file |
| Stage *Unit tests* fails | open the console output: the failing test and its message are printed there |
