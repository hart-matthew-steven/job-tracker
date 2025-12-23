-- Local development only. Runs once when the Postgres volume is empty.
-- Creates the same app/migrator roles used by docker-compose so the backend
-- can connect with least-privilege credentials.

DO
$$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'jobtracker_app') THEN
    CREATE ROLE jobtracker_app LOGIN PASSWORD 'my_fake_app_user_password';
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'jobtracker_migrator') THEN
    CREATE ROLE jobtracker_migrator LOGIN PASSWORD 'my_fake_migrator_password';
  END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO jobtracker_app;
GRANT USAGE, CREATE ON SCHEMA public TO jobtracker_migrator;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO jobtracker_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO jobtracker_app;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO jobtracker_migrator;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO jobtracker_migrator;

ALTER DEFAULT PRIVILEGES FOR ROLE jobtracker_migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO jobtracker_app;
ALTER DEFAULT PRIVILEGES FOR ROLE jobtracker_migrator IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO jobtracker_app;

ALTER DEFAULT PRIVILEGES FOR ROLE jobtracker_migrator IN SCHEMA public
  GRANT ALL ON TABLES TO jobtracker_migrator;
ALTER DEFAULT PRIVILEGES FOR ROLE jobtracker_migrator IN SCHEMA public
  GRANT ALL ON SEQUENCES TO jobtracker_migrator;
-- Local development-only initialization script.
-- Runs automatically on first docker-compose startup (new volume).

CREATE ROLE jobtracker_app LOGIN PASSWORD 'my_fake_app_user_password';
CREATE ROLE jobtracker_migrator LOGIN PASSWORD 'my_fake_migrator_password';

ALTER ROLE jobtracker_app SET search_path TO public;
ALTER ROLE jobtracker_migrator SET search_path TO public;

ALTER DATABASE jobtracker OWNER TO jobtracker_migrator;
ALTER SCHEMA public OWNER TO jobtracker_migrator;

GRANT USAGE ON SCHEMA public TO jobtracker_app;
GRANT CREATE ON SCHEMA public TO jobtracker_migrator;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO jobtracker_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO jobtracker_app;

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO jobtracker_migrator;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO jobtracker_migrator;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO jobtracker_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO jobtracker_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT ALL ON TABLES TO jobtracker_migrator;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT ALL ON SEQUENCES TO jobtracker_migrator;

