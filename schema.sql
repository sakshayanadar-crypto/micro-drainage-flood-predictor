-- MySQL version of the schema (only needed if you want to create it by hand;
-- the app creates these tables automatically on first start).
CREATE DATABASE IF NOT EXISTS flood_predictor CHARACTER SET utf8mb4;
USE flood_predictor;

CREATE TABLE IF NOT EXISTS zones (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL, lat DOUBLE NOT NULL, lng DOUBLE NOT NULL,
  elevation_m DOUBLE NOT NULL, drain_capacity_mm_hr DOUBLE NOT NULL,
  blockage_pct DOUBLE NOT NULL, curve_number INT NOT NULL);

CREATE TABLE IF NOT EXISTS live_data (
  id INT AUTO_INCREMENT PRIMARY KEY, zone_id INT NOT NULL, recorded_at DATETIME NOT NULL,
  rain_1h DOUBLE, rain_24h DOUBLE, forecast_3h DOUBLE,
  temperature DOUBLE, humidity DOUBLE, soil_saturation DOUBLE,
  source VARCHAR(10) NOT NULL DEFAULT 'live',
  FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE, INDEX (zone_id, recorded_at));

CREATE TABLE IF NOT EXISTS predictions (
  id INT AUTO_INCREMENT PRIMARY KEY, zone_id INT NOT NULL, created_at DATETIME NOT NULL,
  risk_score DOUBLE NOT NULL, risk_level VARCHAR(10) NOT NULL, ponding_cm DOUBLE NOT NULL,
  rain_1h DOUBLE, source VARCHAR(10) NOT NULL DEFAULT 'live',
  FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE, INDEX (zone_id, created_at));

CREATE TABLE IF NOT EXISTS alerts (
  id INT AUTO_INCREMENT PRIMARY KEY, zone_id INT NOT NULL, created_at DATETIME NOT NULL,
  level VARCHAR(10) NOT NULL, message VARCHAR(300) NOT NULL,
  FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE, INDEX (created_at));

CREATE TABLE IF NOT EXISTS public_reports (
  id INT AUTO_INCREMENT PRIMARY KEY, zone_id INT NULL, lat DOUBLE NOT NULL, lng DOUBLE NOT NULL,
  water_level_cm INT NOT NULL, description VARCHAR(300), created_at DATETIME NOT NULL,
  FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE SET NULL, INDEX (created_at));
