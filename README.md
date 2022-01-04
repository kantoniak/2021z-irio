# 2021z-irio

## Building with Google Deployment Manager

1. [Set up `gcloud` tool](https://cloud.google.com/sdk/docs/quickstart) if not done yet.
2. Create a [Source Repository](https://source.cloud.google.com/repo/new) (named `alerting-platform`) in the target project.
3. Add remote and push this code to the repository:
    ```bash
    # Update <project> first!
    git remote add google https://source.developers.google.com/p/<project>/r/alerting-platform
    git push --all google
    ```
4. Deploy with Google Deployment Manager:
    ```
    gcloud deployment-manager deployments create prod --config infra/deploy-prod.yaml
    ```
    Deployment may fail if information about just enables API don't propagate immediately. In such case, wait a few minutes and update deployment to create missing resources:
    ```
    gcloud deployment-manager deployments update prod --config infra/deploy-prod.yaml
    ```
5. Enable public access to `WorkInProgress`:
    ```bash
    # `region` has to match the one of the function
    gcloud functions add-iam-policy-binding WorkInProgress \
      --region="europe-central2"
      --member="allUsers" \
      --role="roles/cloudfunctions.invoker"
    ```

### Development

To update deployment (add new objects etc.), use the following:
```
gcloud deployment-manager deployments update prod --config infra/deploy-prod.yaml
```
Note that some changes are irreversible!

You may want to connect to database to create table and insert sample data from `sample-data.sql`:
```bash
# Set <username>!
gcloud sql connect services-instance -d services-db -u <username>
```

To force checking a service, push its numeric ID to the pubsub topic:
```bash
# Set <service-id>!
gcloud pubsub topics publish services-to-check --message="<service-id>"
```

To acknowledge incident as primary admin, make an HTTP request to `https://<region>-<project>.cloudfunctions.net/WorkInProgress?key=<key>`.