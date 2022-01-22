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
4. Contact us for a key to decrypt the file(this file might not be present in repository for security reasons). 
For convenience reasons it will be posted here: `4d5c0d87-9dc9-43fe-b3ca-52688e866006`

5. Deploy with Google Deployment Manager:
    First, you need to update the preexisting config with data(to do this step you will need the afromentioned key)
    ```
    chmod +x ./update_config.sh && ./update_config.sh
    ```
    After that, run this command to create the project
    ```
    gcloud deployment-manager deployments create prod --config infra/deploy-prod-updated.yaml
    ```
    Deployment may fail if information about just enables API don't propagate immediately. In such case, wait a few minutes and update deployment to create missing resources:
    ```
    gcloud deployment-manager deployments update prod --config infra/deploy-prod-updated.yaml
    ```
    It may also fail due to the insufficient permissions of a service account used by Deployment Manager to create App Engine application. In this case, you should add Owner permissions to `[PROJECT_NUMBER]@cloudservices.gserviceaccount.com` service account:
    ```
    gcloud projects add-iam-policy-binding [PROJECT_ID] \
        --member=serviceAccount:[PROJECT_NUMBER]@cloudservices.gserviceaccount.com --role=roles/owner
    ```
    ** IMPORTANT **

    After you've successfully deployed the project, delete `infra/deploy-prod-updated.yaml`. Not doing it poses a security risk!


6. Enable public access to `WorkInProgress`:
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

## Testing

To run unit tests use the following commands in the root directory:
```bash
. ./set_test_env.sh
pytest
```
