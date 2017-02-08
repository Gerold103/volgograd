CREATE DATABASE volgograd;

USE volgograd;

CREATE TABLE reports (id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
	author_id INT UNSIGNED,
	date DATE,
	temp_average_air DOUBLE,
	temp_average_water DOUBLE,
	expected_temp_air_day DOUBLE,
	expected_temp_air_night DOUBLE,
	expected_temp_air_all_day DOUBLE,
	forecast_date DATE,
	forecast_weather TEXT,
	forecast_direction VARCHAR(10),
	forecast_speed VARCHAR(10),
	forecast_temp_day_from DOUBLE,
	forecast_temp_day_to DOUBLE,
	forecast_temp_night_from DOUBLE,
	forecast_temp_night_to DOUBLE,
	FOREIGN KEY (autor_id) REFERENCES users(id) ON DELETE SET NULL,
	UNIQUE (date)) CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE districts (id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
	name TEXT,
	UNIQUE (name(50))) CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE boiler_rooms (id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
	district_id INT UNSIGNED,
	name TEXT,
	UNIQUE (district_id, name(50)),
	FOREIGN KEY (district_id) REFERENCES districts(id) ON DELETE CASCADE)
	CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE boiler_room_reports(id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
	boiler_room_id INT UNSIGNED,
	report_id INT UNSIGNED,
	T1 DOUBLE, T2 DOUBLE,
	gas_pressure DOUBLE,
	boilers_all INT UNSIGNED,
	boilers_in_use INT UNSIGNED,
	torchs_in_use INT UNSIGNED,
	boilers_reserve INT UNSIGNED,
	boilers_in_repair INT UNSIGNED,
	net_pumps_in_work INT UNSIGNED,
	net_pumps_reserve INT UNSIGNED,
	net_pumps_in_repair INT UNSIGNED,
	all_day_expected_temp1 DOUBLE, all_day_expected_temp2 DOUBLE,
	all_day_real_temp1 DOUBLE, all_day_real_temp2 DOUBLE,
	all_night_expected_temp1 DOUBLE, all_night_expected_temp2 DOUBLE,
	all_night_real_temp1 DOUBLE, all_night_real_temp2 DOUBLE,
	net_pressure1 DOUBLE, net_pressure2 DOUBLE,
	net_water_consum_expected_ph DOUBLE,
	net_water_consum_real_ph DOUBLE,
	make_up_water_consum_expected_ph DOUBLE,
	make_up_water_consum_real_ph DOUBLE,
	make_up_water_consum_real_pd DOUBLE,
	make_up_water_consum_real_pm DOUBLE,
	hardness DOUBLE,
	transparency DOUBLE,
	FOREIGN KEY (boiler_room_id) REFERENCES boiler_rooms(id) ON DELETE CASCADE,
	FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE)
	CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE users (id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
	email VARCHAR(100), password TEXT, salt VARCHAR(20), name TEXT,
	rights INT UNSIGNED,
	UNIQUE (email))
	CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
