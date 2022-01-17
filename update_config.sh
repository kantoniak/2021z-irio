openssl enc -d -aes-256-cbc -pbkdf2 -in secure_vars -out private_vars.txt &&
source private_vars.txt && export db_username db_password db_database &&
sed "s/__DB_USERNAME_NOT_YET_PRESENT/$db_username/;s/__DB_PASSWORD_NOT_YET_PRESENT/$db_password/;s/__DB_DATABASE_NOT_YET_PRESENT/$db_database/" infra/deploy-prod.yaml > infra/deploy-prod-updated.yaml &&
rm -f private_vars.txt &&
unset db_username db_password db_database