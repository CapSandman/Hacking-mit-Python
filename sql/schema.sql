-- SITES (solar plants)
CREATE TABLE IF NOT EXISTS sites (
id INT AUTO_INCREMENT PRIMARY KEY,
name VARCHAR(120) NOT NULL,
location VARCHAR(255) NULL,
capacity_kwp DECIMAL(10,2) NOT NULL,
timezone VARCHAR(64) NOT NULL DEFAULT 'Europe/Berlin',
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;


-- METERS (per site)
CREATE TABLE IF NOT EXISTS meters (
id INT AUTO_INCREMENT PRIMARY KEY,
site_id INT NOT NULL,
name VARCHAR(120) NOT NULL,
interval_minutes INT NOT NULL DEFAULT 15,
unit VARCHAR(16) NOT NULL DEFAULT 'kWh',
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
CONSTRAINT fk_meters_site FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE,
INDEX idx_meters_site (site_id)
) ENGINE=InnoDB;


-- READINGS (15-min energy for a meter)
CREATE TABLE IF NOT EXISTS readings_15m (
id BIGINT AUTO_INCREMENT PRIMARY KEY,
meter_id INT NOT NULL,
ts DATETIME NOT NULL,
value_kwh DECIMAL(12,4) NOT NULL,
CONSTRAINT fk_readings_meter FOREIGN KEY (meter_id) REFERENCES meters(id) ON DELETE CASCADE,
UNIQUE KEY uniq_meter_ts (meter_id, ts),
INDEX idx_readings_meter_ts (meter_id, ts)
) ENGINE=InnoDB;


-- ALARMS (very simple MVP, optional persistence)
CREATE TABLE IF NOT EXISTS alarms (
id BIGINT AUTO_INCREMENT PRIMARY KEY,
site_id INT NOT NULL,
meter_id INT NULL,
code VARCHAR(64) NOT NULL,
severity ENUM('info','warn','crit') NOT NULL DEFAULT 'warn',
message TEXT NOT NULL,
raised_at DATETIME NOT NULL,
resolved_at DATETIME NULL,
CONSTRAINT fk_alarms_site FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE,
CONSTRAINT fk_alarms_meter FOREIGN KEY (meter_id) REFERENCES meters(id) ON DELETE SET NULL,
INDEX idx_alarms_site_raised (site_id, raised_at)
) ENGINE=InnoDB;


-- USERS (basic login)
CREATE TABLE IF NOT EXISTS users2 (
id INT AUTO_INCREMENT PRIMARY KEY,
username VARCHAR(64) NOT NULL UNIQUE,
password VARCHAR(255) NOT NULL,
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS site_energy_daily (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  site_id INT NOT NULL,
  day DATE NOT NULL,
  energy_kwh DECIMAL(14,4) NOT NULL,
  UNIQUE KEY uniq_site_day (site_id, day),
  INDEX idx_site_day (site_id, day),
  CONSTRAINT fk_sed_site FOREIGN KEY (site_id)
    REFERENCES sites(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- users_prof (prof login)
CREATE TABLE IF NOT EXISTS users_prof(
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(64) NOT NULL UNIQUE,
  password VARCHAR(255) NOT NULL
) ENGINE=InnoDB;

INSERT INTO users_prof (username, password) VALUES ('prof', 'test123');

CREATE TABLE IF NOT EXISTS testitems (
  id INT AUTO_INCREMENT PRIMARY KEY,
  priority VARCHAR(32),
  username VARCHAR(80),
  title VARCHAR(255),
  info TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


INSERT INTO testitems (priority, username, title, info) VALUES
('high', 'mateo', 'Inverter alarm', 'DC string undervoltage detected...'),
('low',  'admin', 'Note', 'OK. <script>alert(1)</script> this is showing up as text.');

ALTER TABLE users
ADD COLUMN active TINYINT(1) NOT NULL DEFAULT 1;

SHOW COLUMNS FROM users;
