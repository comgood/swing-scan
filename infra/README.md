# Infrastructure: first deploy (run by you, not by agents)

Spec 0001 keeps all cloud setup in your hands: no agent holds AWS, Vercel, or Alpaca credentials. These steps create the hello world deploy for scope feature 1. Automated deploys from GitHub Actions with OIDC come with scope feature 15.

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

The image must be built on x86: Polars segfaults under Docker's x86 emulation on Apple Silicon, so `make build-api` fails on an M series Mac. CI builds and smoke tests the real image on an x86 runner, and on every push to `main` (or a manual run of the CI workflow on any branch) it keeps that image as an artifact for 7 days.

```bash
FULL=$(git rev-parse origin/main)     # the commit to deploy; its CI run must be green
SHA=${FULL:0:7}                        # the image tag, used again in step 6
REPO=<account-id>.dkr.ecr.ap-southeast-1.amazonaws.com/swing-scan-api
RUN=$(gh run list --workflow CI --commit $FULL --event push --json databaseId -q '.[0].databaseId')
# (no run for that commit: gh workflow run CI --ref main, then repeat the line above with --event workflow_dispatch)
gh run download $RUN --name api-image-$FULL --dir /tmp/api-image
gunzip -c /tmp/api-image/api-image.tar.gz | docker load    # loads swing-scan-api:latest (linux/amd64)
docker tag swing-scan-api:latest $REPO:$SHA
aws ecr get-login-password --region ap-southeast-1 | docker login --username AWS --password-stdin ${REPO%/*}
docker push $REPO:$SHA
```

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
  --environment 'Variables={DATA_MODE=synthetic,ALLOWED_ORIGINS=https://<your-vercel-domain>,ALLOWED_ORIGIN_REGEX=^https://swing-scan-[a-z0-9-]+\.vercel\.app$}'

# Only if step 2 allows it:
aws lambda put-function-concurrency --function-name swing-scan-api --region ap-southeast-1 \
  --reserved-concurrent-executions 5

aws lambda create-function-url-config --function-name swing-scan-api --region ap-southeast-1 \
  --auth-type NONE
aws lambda add-permission --function-name swing-scan-api --region ap-southeast-1 \
  --statement-id public-url --action lambda:InvokeFunctionUrl \
  --principal '*' --function-url-auth-type NONE

aws logs put-retention-policy --log-group-name /aws/lambda/swing-scan-api \
  --retention-in-days 7 --region ap-southeast-1
```

Check it: `make smoke API_URL=<function-url>`. Record the first (cold) response time in the README; over 8 s reopens ADR-001.

## 7. Vercel project

- Import the GitHub repo in Vercel; set **Root Directory** to `apps/web` (keep "include files outside the root directory" on).
- Framework preset Next.js; Node 24.
- Env var `NEXT_PUBLIC_API_URL` = the Function URL, for Production and Preview.
- After the first deploy, put the production domain into the Lambda's `ALLOWED_ORIGINS` and adjust `ALLOWED_ORIGIN_REGEX` to your preview URL pattern.

## 8. Throttle alarm (abuse signal)

Create a CloudWatch alarm on the `Throttles` metric for `swing-scan-api` (sum over 5 minutes > 0) that emails you.
