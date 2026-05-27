void initLog() {
  start_pc_timestamp_ms = System.currentTimeMillis();
  session_id = "session_" + timestampForFile();

  File dir = new File(sketchPath("logs"));
  if (!dir.exists()) {
    dir.mkdirs();
  }

  input_log_path = sketchPath("logs/" + session_id + "_input.csv");
  game_log_path = sketchPath("logs/" + session_id + "_game.csv");

  input_log_writer = createWriter(input_log_path);
  input_log_writer.println(inputCsvHeader());
  input_log_writer.flush();

  game_log_writer = createWriter(game_log_path);
  game_log_writer.println(gameCsvHeader());
  game_log_writer.flush();

  println("INPUT LOG: " + input_log_path);
  println("GAME LOG: " + game_log_path);
}

String inputCsvHeader() {
  return "pc_timestamp_ms,elapsed_ms,microbit_runtime_ms,frame_count,serial_valid,"
    + "serial_column_count,serial_valid_count,serial_invalid_count,control_age_ms,"
    + "ax_raw,ay_raw,az_raw,light_raw,temp_raw,shake_raw,pitch_raw,roll_raw,btnA_raw,btnB_raw,"
    + "control_x_raw,control_y_raw,"
    + "input_x_smooth,input_y_smooth,tilt_x,speed_modifier,btnA_pressed,btnB_pressed,shake_event,light_shield,"
    + "serial_status,last_serial_line";
}

String gameCsvHeader() {
  return "pc_timestamp_ms,elapsed_ms,frame_count,"
    + "player_x,player_y,player_vx,"
    + "target_type,target_x,target_y,target_dx,target_dy,target_distance,"
    + "bullet_active,bullet_x,bullet_y,"
    + "score,miss_count,shield_active,event_type,event_value";
}

void writeLog() {
  updateTargetMetrics();
  writeInputLog();
  writeGameLog();
}

void writeInputLog() {
  if (input_log_writer == null) {
    return;
  }

  String[] row = {
    str(System.currentTimeMillis()),
    str(System.currentTimeMillis() - start_pc_timestamp_ms),
    str(microbit_runtime_ms),
    str(frameCount),
    str(serial_valid),
    str(serial_column_count),
    str(serial_valid_count),
    str(serial_invalid_count),
    str(controlAgeMs()),

    fmt(ax_raw),
    fmt(ay_raw),
    fmt(az_raw),
    str(light_raw),
    str(temp_raw),
    str(shake_raw),
    fmt(pitch_raw),
    fmt(roll_raw),
    str(btnA_raw),
    str(btnB_raw),
    fmt(control_x_raw),
    fmt(control_y_raw),

    fmt(input_x_smooth),
    fmt(input_y_smooth),
    fmt(tilt_x),
    fmt(speed_modifier),
    str(btnA_pressed),
    str(btnB_pressed),
    str(shake_event),
    str(light_shield),
    csvEscape(serial_status),
    csvEscape(last_serial_line)
  };

  input_log_writer.println(join(row, ","));
  input_rows_since_flush++;

  if (input_rows_since_flush >= LOG_FLUSH_EVERY_FRAMES) {
    input_log_writer.flush();
    input_rows_since_flush = 0;
  }
}

void writeGameLog() {
  if (game_log_writer == null) {
    return;
  }

  String[] row = {
    str(System.currentTimeMillis()),
    str(System.currentTimeMillis() - start_pc_timestamp_ms),
    str(frameCount),
    fmt(player_x),
    fmt(player_y),
    fmt(player_vx),

    csvEscape(target_type),
    fmt(target_x),
    fmt(target_y),
    fmt(target_dx),
    fmt(target_dy),
    fmt(target_distance),

    bullet_active ? "1" : "0",
    fmt(bullet_x),
    fmt(bullet_y),

    str(score),
    str(miss_count),
    shield_active ? "1" : "0",
    csvEscape(event_type),
    csvEscape(event_value)
  };

  game_log_writer.println(join(row, ","));
  game_rows_since_flush++;

  if (game_rows_since_flush >= LOG_FLUSH_EVERY_FRAMES) {
    game_log_writer.flush();
    game_rows_since_flush = 0;
  }
}

void closeLog() {
  if (input_log_writer != null) {
    input_log_writer.flush();
    input_log_writer.close();
    input_log_writer = null;
  }

  if (game_log_writer != null) {
    game_log_writer.flush();
    game_log_writer.close();
    game_log_writer = null;
  }
}

String fmt(float value) {
  if (!isFinite(value)) {
    return "";
  }
  return nf(value, 0, 4);
}

String csvEscape(String value) {
  if (value == null) {
    return "";
  }

  String s = value.replace("\"", "\"\"");
  if (s.indexOf(',') >= 0 || s.indexOf('"') >= 0 || s.indexOf('\n') >= 0) {
    return "\"" + s + "\"";
  }
  return s;
}

String timestampForFile() {
  return nf(year(), 4)
    + nf(month(), 2)
    + nf(day(), 2)
    + "_"
    + nf(hour(), 2)
    + nf(minute(), 2)
    + nf(second(), 2);
}
