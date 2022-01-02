# 2021z-irio

## Building with Google Deployment Manager

1. Create a [Source Repository](https://source.cloud.google.com/repo/new) (named `alerting-platform`) in the target project.
2. Add remote and push this code to the repository.
3. Deploy with Google Deployment Manager:
    ```
    gcloud deployment-manager deployments update prod --config infra/deploy-prod.yaml
    ```
4. Enable public access to `WorkInProgress`:
    ```
    gcloud functions add-iam-policy-binding WorkInProgress \
      --region="europe-central2"
      --member="allUsers" \
      --role="roles/cloudfunctions.invoker"
    ```
5. You may want to connect to database to create table and insert sample data from `sample-data.sql`:
    ```
    gcloud sql connect services-instance -d services-db -u <username>
    ```