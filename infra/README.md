# Infrastructure: deploy setup (run by you, not by agents)

Spec 0001 keeps all cloud setup in your hands: no agent holds AWS, Vercel, or Alpaca credentials. Steps 1 to 8 are the first deploy (scope feature 1, done on 2026-10-09). Step 9 turns on automated deploys from GitHub Actions with OIDC (scope feature 15); after that, step 4 is only the manual fallback.

What runs today: Lambda `swing-scan-api` (x86_64, 2048 MB, 30 s, no reserved concurrency because the account quota is 10), its public Function URL, ECR repo `swing-scan-api` (images tagged with the 7 character commit SHA), the web app on Vercel (deployed by Vercel from Git), a $1 budget alarm, and a `Throttles` alarm that emails you.

Region: `ap-southeast-1`. Architecture: `x86_64`. Replace `<account-id>` with your AWS account ID.

## Before you start

- An AWS account with the AWS CLI v2 configured (`aws configure` or `aws sso login`).
- Docker Desktop running, and the GitHub CLI (`gh auth login`) to download the CI built image.
- A Vercel account linked to the GitHub repo.

## 1. Budget alarm first ($1)

Create a monthly cost budget of $1 with an email alert in the AWS console (Billing, Budgets), or with `aws budgets create-budget`. Do this before anything else.

## 2. Check the Lambda concurrency quota

```bash
aws lambda get-account-settings --region ap-southeast-1 \
  --query 'AccountLimit.ConcurrentExecutions'
```

If the result is above 15, reserve 5 for this function in step 6. If it is 10 (common on new accounts), skip the reservation and request a quota increase in Service Quotas.

## 3. ECR repository with a lifecycle policy

```bash
aws ecr create-repository --repository-name swing-scan-api --region ap-southeast-1
aws ecr put-lifecycle-policy --repository-name swing-scan-api --region ap-southeast-1 \
  --lifecycle-policy-text '{"rules":[{"rulePriority":1,"description":"keep last 5","selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":5},"action":{"type":"expire"}}]}'
```

## 4. Get the image from CI and push it, tagged with the git commit

Once step 9 is done, the Deploy API workflow does this for you after every green CI run on `main`. Keep this step as the fallback for when the workflow can't run.

The image must be built on x86: Polars segfaults under Docker's x86 emulation on Apple Silicon, so `make build-api` fails on an M series Mac. CI builds and smoke tests the real image on an x86 runner, and on every push to `main` (or a manual run of the CI workflow on any branch) it keeps that image as an artifact for 7 days.

```bash
git fetch origin
FULL=$(git rev-parse origin/main)
SHA=${FULL:0:7}
REPO=<account-id>.dkr.ecr.ap-southeast-1.amazonaws.com/swing-scan-api
RUN=$(gh run list --workflow CI --commit $FULL --event push --json databaseId -q '.[0].databaseId')
gh run watch $RUN --exit-status
gh run download $RUN --name api-image-$FULL --dir /tmp/api-image
gunzip -c /tmp/api-image/api-image.tar.gz | docker load
docker tag swing-scan-api:latest $REPO:$SHA
aws ecr get-login-password --region ap-southeast-1 | docker login --username AWS --password-stdin ${REPO%/*}
docker push $REPO:$SHA
```

`FULL` is the commit to deploy and `SHA` is the image tag that step 6 uses again. `gh run watch` waits for that commit's CI run and stops if it failed. `docker load` gives you `swing-scan-api:latest` (linux/amd64). If the commit has no push run, start one with `gh workflow run CI --ref main` and use `--event workflow_dispatch` in the `RUN=` line. The block has no inline comments, because zsh treats `#` as a command unless `setopt interactive_comments` is on.

On an x86 machine you can still build it yourself: `make build-api API_IMAGE=$REPO:$SHA`. To smoke test locally on Apple Silicon, use `make build-api-local && make smoke-image API_IMAGE=swing-scan-api:local-arm64`.

## 5. Execution role

```bash
aws iam create-role --role-name swing-scan-api-exec \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
aws iam attach-role-policy --role-name swing-scan-api-exec \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
```

## 6. Lambda function and Function URL

```bash
aws lambda create-function --function-name swing-scan-api --region ap-southeast-1 \
  --package-type Image --code ImageUri=$REPO:$SHA \
  --role arn:aws:iam::<account-id>:role/swing-scan-api-exec \
  --architectures x86_64 --memory-size 2048 --timeout 30 \
  --environment '{"Variables":{"DATA_MODE":"synthetic","ALLOWED_ORIGINS":"https://<your-vercel-domain>","ALLOWED_ORIGIN_REGEX":"^https://swing-scan-[a-z0-9-]+\\.vercel\\.app$"}}'
```

The environment is JSON, not the CLI's `Key=Value` shorthand: the shorthand parser reads the `[` in the regex as a list and fails. The `\\.` becomes the regex's `\.` once the JSON is parsed. If you don't know your Vercel domain yet, use `https://swing-scan.vercel.app` and fix it after step 7 with `aws lambda update-function-configuration` and the same `--environment` value.

Only if step 2 allows it:

```bash
aws lambda put-function-concurrency --function-name swing-scan-api --region ap-southeast-1 \
  --reserved-concurrent-executions 5
```

Then the public Function URL:

```bash
aws lambda create-function-url-config --function-name swing-scan-api --region ap-southeast-1 \
  --auth-type NONE
aws lambda add-permission --function-name swing-scan-api --region ap-southeast-1 \
  --statement-id public-url --action lambda:InvokeFunctionUrl \
  --principal '*' --function-url-auth-type NONE
aws lambda add-permission --function-name swing-scan-api --region ap-southeast-1 \
  --statement-id public-url-invoke --action lambda:InvokeFunction \
  --principal '*' --invoked-via-function-url

aws logs put-retention-policy --log-group-name /aws/lambda/swing-scan-api \
  --retention-in-days 7 --region ap-southeast-1
```

Since October 2025 a new public Function URL needs both statements, `lambda:InvokeFunctionUrl` and `lambda:InvokeFunction` (restricted to calls through the URL); with only the first, every request gets 403 Forbidden. The log group only exists after the first invocation, so if `put-retention-policy` says it does not exist, call `/api/v1/health` once and run it again.

Check it: `make smoke API_URL=<function-url>`. It prints the first call and warm call times, and the size of each response. A first call over 8 s reopens ADR-001.

**Measured cold start:** about 3.1 s for the first call from outside AWS on 2026-10-09 (2048 MB, x86_64, synthetic market loaded at import). That is under the 6 s goal and well under ADR-001's 8 s limit. Every automated deploy prints a fresh first call time in its run summary, because the first call after `update-function-code` lands on a new execution environment.

## 7. Vercel project

- Import the GitHub repo in Vercel; set **Root Directory** to `apps/web` (keep "include files outside the root directory" on).
- Framework preset Next.js; Node 24.
- Env var `NEXT_PUBLIC_API_URL` = the Function URL, for Production and Preview.
- After the first deploy, put the production domain into the Lambda's `ALLOWED_ORIGINS` and adjust `ALLOWED_ORIGIN_REGEX` to your preview URL pattern.

## 8. Throttle alarm (abuse signal)

Create a CloudWatch alarm on the `Throttles` metric for `swing-scan-api` (sum over 5 minutes > 0) that emails you.

## 9. Automated deploys with GitHub OIDC (once)

`.github/workflows/deploy.yml` (Deploy API) runs after CI passes on a push to `main`. It reuses the image CI built and smoked (artifact `api-image-<sha>`), pushes it to ECR as `<7 char sha>`, runs `aws lambda update-function-code` and waits for the update, then runs `make smoke` against the Function URL. It holds no AWS keys: it asks GitHub for an OIDC token and trades it for a short session on a deploy role that trusts only this repo's `main` branch. Until you set the `AWS_ROLE_ARN` variable the job is skipped, so `main` stays green.

The policies live in `infra/iam/`: `deploy-trust.json` (who may assume the role: GitHub's OIDC provider, audience `sts.amazonaws.com`, subject `repo:comgood/swing-scan:ref:refs/heads/main`) and `deploy-policy.json` (what the role may do: log in to ECR, push to and read only the `swing-scan-api` repository, and update and read only the `swing-scan-api` function). The two repository policy actions are there because Lambda adds its own pull permission to the repository through the caller when it is missing.

Run these from the repo root, with the same AWS CLI login as steps 1 to 8:

```bash
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com
sed "s/ACCOUNT_ID/${ACCOUNT}/g" infra/iam/deploy-trust.json > /tmp/deploy-trust.json
sed "s/ACCOUNT_ID/${ACCOUNT}/g" infra/iam/deploy-policy.json > /tmp/deploy-policy.json
aws iam create-role --role-name swing-scan-deploy \
  --assume-role-policy-document file:///tmp/deploy-trust.json
aws iam put-role-policy --role-name swing-scan-deploy --policy-name swing-scan-deploy \
  --policy-document file:///tmp/deploy-policy.json
gh variable set AWS_ROLE_ARN --body "arn:aws:iam::${ACCOUNT}:role/swing-scan-deploy"
gh variable set API_URL --body https://fmcpmff6uu77byyy45vo6tsocu0fadzx.lambda-url.ap-southeast-1.on.aws
```

If `create-open-id-connect-provider` says `EntityAlreadyExists`, the account already has GitHub's provider; skip it and go on. No thumbprint is needed: AWS checks GitHub's certificate against its trusted authorities. Write `${ACCOUNT}` with braces: in zsh, `$ACCOUNT:role` would read `:r` as a modifier. The workflow defaults `AWS_REGION`, `ECR_REPOSITORY` and `LAMBDA_FUNCTION_NAME` to `ap-southeast-1` and `swing-scan-api`; set those variables only if yours differ. These are repository variables, not secrets: nothing here is sensitive.

Try it once by hand, then watch the run:

```bash
git fetch origin
gh workflow run deploy.yml --ref main -f sha=$(git rev-parse --short origin/main)
gh run watch --exit-status
```

`gh run watch` asks which run to follow; pick the Deploy API one.

The run summary shows the smoke output, with the first call (cold) and warm times. The same manual run is the rollback: pass an older commit, and the workflow reuses its image from ECR (the lifecycle policy keeps the last 5) or, failing that, its CI artifact (kept 7 days).

## 10. Warm up and keep alive

The warm up ping is the web app's (spec 0001): it calls `GET /api/v1/health` on page load and shows a "warming up" state while the cold start runs, so nothing in AWS keeps the function warm, and nothing needs to.

`.github/workflows/keep-alive.yml` calls `/api/v1/health` once a week (Monday 03:17 UTC). That is not to keep it warm. A container image function that gets no calls for several weeks goes Inactive, and Lambda then rejects the next call while it optimizes the image again, which would spoil the first demo visit after a quiet spell. One call a week costs $0 (the Lambda always free tier, and Actions minutes are free on a public repo). It is skipped until the `API_URL` variable is set (step 9).

GitHub turns off scheduled workflows in a public repo after 60 days with no repository activity. Any push to `main` resets the clock. If it was turned off, GitHub emails you; turn it back on with `gh workflow enable keep-alive.yml`. The deploy workflow is triggered by CI, not by a schedule, so the rule never touches it.

## 11. Day 1 checks (doc 02 task F6), outcome

Checked on 2026-10-09:

- **Alpaca terms.** Alpaca's market data docs confirm the free Basic plan serves historical SIP bars back to 2016, holds back only the latest 15 minutes (no effect on daily bars), and allows 200 calls a minute. The docs grant no right to redistribute or display the data to others, so live data stays personal, non commercial and local only, as doc 01 already says: never committed, never hosted, never in the GIF (D-5, D-6). Read the market data agreement in your Alpaca account before you ever change that.
- **GitHub's 60 day rule.** Doc 02 planned no scheduled workflow, so it was not applicable. Feature 15 adds one (step 10); the rule now applies to that workflow only, and step 10 says how to keep it on.
- **Lambda 6 MB limit.** A synchronous call (which a Function URL in buffered mode is) can return at most 6 MB. The guards: the contract caps every list (scan rows ≤ 500 in `engine/src/engine/contracts/scan.py`; equity and benchmark points ≤ 500, trades ≤ 2,000 and baseline trades ≤ 2,000 in `engine/src/engine/contracts/backtest.py`) and allows at most 6 configs; the acceptance tests for B-13 (`tests/acceptance/test_backtest.py`) and X-7 (`tests/acceptance/test_exit_lab.py`) assert each response's uncompressed JSON is under 6,000,000 bytes on a 500 ticker, 5 year market; and `scripts/smoke.sh` fails if a deployed response (health, scan, a 5 config exit lab) reaches 6,000,000 bytes uncompressed. On the seed 42 market that exit lab is about 0.63 MB, and `GZipMiddleware` shrinks it again for browsers.
- **Cold start.** See step 6: about 3.1 s.
