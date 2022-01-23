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
    It may also fail due to the insufficient permissions of a service account used by Deployment Manager to create App Engine application or to assign IAM roles (see `infra/cloud-function.jinja`). In this case, you should add Owner permissions to `[PROJECT_NUMBER]@cloudservices.gserviceaccount.com` service account:
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
. ./test.sh
```

To run stress/load tests:
0. Build the project using the afromentioned way.
1. After, you need to build the mockup service. 
```bash
cd mockup_service
gcloud app deploy
cd ..
```
At this point there should be an application listening on `https://[PROJECT_ID].appspot.com/ping`
2. Use the following commands in the root directory:
```bash
. ./set_test_env.sh # Set enviromental variables, you might want to tinker some of those if neccessary
export BUCKET="testing-bucket-for-ds"
export EXAMPLE_NAME="example_name"
python3 ./Tests/stress_test.py 0 desired_pool ${EXAMPLE_NAME} # Create an SQL file to create multiple listeners on our mockup service
gsutil mb gs://$BUCKET # This step might not be needed or might need replacing in the name.
gsutil cp ${EXAMPLE_NAME}.sql gs://${BUCKET} # Upload to SQL file to a newly created bucket
# https://stackoverflow.com/questions/50828098/permissions-for-google-cloud-sql-import-using-service-accounts
export SA_NAME=$(gcloud sql instances describe [YOUR_DB_INSTANCE_NAME] --project=[YOUR_PROJECT_ID] --format="value(serviceAccountEmailAddress)") # Bunch of permission magic
gsutil acl ch -u ${SA_NAME}:R gs://${BUCKET}
gsutil acl ch -u ${SA_NAME}:R gs://${BUCKET}/${EXAMPLE_NAME}.sql
gcloud sql import sql services-instance gs://${BUCKET}/${EXAMPLE_NAME}.sql --database=services-db --user=services_user
```
After those steps the Database should be updated with our listeners

3. Now begin listening
```bash
python3 ./Tests/stress_test.py 1
```
And wait. When the application has finished, check the dashboards in your project to see how did the functions behave under the `desired_pool` load. Especially important are `Invocations/second` - for seeing how many invocations end with a success and `Execution time` - for seeing how fast are we running our functions.

Exact values of `desired_pool` for load/stress testing must be constructed with an expected load in mind - which we don't know currently.
