#!/usr/bin/env bash
cd /home/openclaw/lodestar-pr10516
L=/home/openclaw/.openclaw/workspace/notes/pr10516-docker
C=$(git rev-parse HEAD)
s=$(date +%s); docker build --pull -t lodestar:pr10516-prod --build-arg COMMIT=$C . > $L/prod-build.log 2>&1; echo "prod exit $? after $(( $(date +%s) - s ))s" > $L/prod-result.txt
docker run --rm lodestar:pr10516-prod --version > $L/prod-run.txt 2>&1; echo "prod run exit $?" >> $L/prod-run.txt
docker run --rm --entrypoint sh lodestar:pr10516-prod -c 'echo NODE_OPTIONS=$NODE_OPTIONS; node --version' >> $L/prod-run.txt 2>&1
s=$(date +%s); docker build --pull -f Dockerfile.dev -t lodestar:pr10516-dev --build-arg COMMIT=$C . > $L/dev-build.log 2>&1; echo "dev exit $? after $(( $(date +%s) - s ))s" > $L/dev-result.txt
touch $L/all-done
