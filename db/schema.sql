-- PostGIS schema for closed transport matching MVP
-- SRID: 4326 (WGS84, lon/lat)

CREATE EXTENSION IF NOT EXISTS postgis;

-- Users
CREATE TABLE IF NOT EXISTS users (
  id            BIGSERIAL PRIMARY KEY,
  handle        TEXT UNIQUE NOT NULL,
  role          TEXT NOT NULL CHECK (role IN ('courier','sender','admin')),
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Courier routes
CREATE TABLE IF NOT EXISTS routes (
  id            BIGSERIAL PRIMARY KEY,
  courier_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title         TEXT,
  start_point   geometry(Point, 4326) NOT NULL,
  end_point     geometry(Point, 4326) NOT NULL,
  geom          geometry(LineString, 4326) NOT NULL,
  distance_m    DOUBLE PRECISION NOT NULL,
  duration_s    DOUBLE PRECISION NOT NULL,
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_routes_geom_gist
  ON routes USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_routes_active
  ON routes (is_active);
CREATE INDEX IF NOT EXISTS idx_routes_courier
  ON routes (courier_id);

-- Parcels
CREATE TABLE IF NOT EXISTS parcels (
  id            BIGSERIAL PRIMARY KEY,
  sender_id     BIGINT REFERENCES users(id) ON DELETE SET NULL,
  pickup_point  geometry(Point, 4326) NOT NULL,
  drop_point    geometry(Point, 4326) NOT NULL,
  status        TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','offered','accepted','rejected','cancelled')),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_parcels_pickup_gist
  ON parcels USING GIST (pickup_point);
CREATE INDEX IF NOT EXISTS idx_parcels_drop_gist
  ON parcels USING GIST (drop_point);
CREATE INDEX IF NOT EXISTS idx_parcels_status
  ON parcels (status);

-- Assignments
CREATE TABLE IF NOT EXISTS assignments (
  id            BIGSERIAL PRIMARY KEY,
  parcel_id     BIGINT NOT NULL REFERENCES parcels(id) ON DELETE CASCADE,
  route_id      BIGINT NOT NULL REFERENCES routes(id) ON DELETE CASCADE,
  status        TEXT NOT NULL DEFAULT 'offered'
    CHECK (status IN ('offered','accepted','rejected','expired')),
  delta_distance_m DOUBLE PRECISION,
  delta_duration_s DOUBLE PRECISION,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_assignments_parcel
  ON assignments (parcel_id);
CREATE INDEX IF NOT EXISTS idx_assignments_route
  ON assignments (route_id);
