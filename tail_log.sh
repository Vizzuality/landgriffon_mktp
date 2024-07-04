#!/bin/bash

while true; do
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=landgriffon-mktp" \
    --limit 100 \
    --project=landgriffon \
    --format="value(timestamp, textPayload)" \
    --freshness="1s" \
    --order="desc"
  #sleep 60
done
