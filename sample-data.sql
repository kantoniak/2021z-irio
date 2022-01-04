-- Functions will create this table on first call
CREATE TABLE IF NOT EXISTS "services" (
    "id" INT NOT NULL,
    "name" VARCHAR(256) NOT NULL,
    "url" TEXT NOT NULL,
    "primary_admin_email" VARCHAR(254) NOT NULL,
    "secondary_admin_email" VARCHAR(254) NOT NULL,
    "last_time_responsive" TIMESTAMP NULL,
    "being_worked_on" BOOLEAN NOT NULL DEFAULT FALSE,
    "primary_admin_key" UUID NULL,
    CONSTRAINT "services_pk" PRIMARY KEY (id)
);

INSERT INTO "services" ("id", "name", "url", "primary_admin_email", "secondary_admin_email", "last_time_responsive", "being_worked_on", "primary_admin_key") VALUES
    (1, 'example', 'https://example.com/', 'admin1@example.com', 'admin2@example.com', NULL, FALSE, '6d18c09e-f47b-41ba-a293-fd6c978c1e66');