-- AGL App Store – multi-database initialisation
-- Runs only on a fresh volume (postgres entrypoint skips it if data already exists)
CREATE DATABASE flatpak_repo OWNER pensagl;
GRANT ALL PRIVILEGES ON DATABASE flatpak_repo TO pensagl;
