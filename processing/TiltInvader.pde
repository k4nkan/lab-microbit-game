import processing.serial.*;
import java.io.File;

void setup() {
  size(800, 600);
  pixelDensity(1);
  frameRate(FRAME_RATE);

  ui_font = createPlatformFont(14);
  textFont(ui_font);

  initLog();
  initSerial();
  resetGame();
}

void draw() {
  event_type = "none";
  event_value = "";

  processInput();
  updateGame();
  drawGame();
  writeLog();

  serial_valid = 0;
}

void initSerial() {
  println("=== Serial Ports ===");
  printArray(Serial.list());

  String port_name = findMicrobitPort();
  if (port_name == null) {
    println("micro:bit port not found.");
    serial_ready = false;
    serial_status = "not connected";
    return;
  }

  try {
    serial_port = new Serial(this, port_name, SERIAL_BAUD);
    serial_port.clear();
    serial_port.bufferUntil('\r');
    serial_ready = true;
    serial_status = "waiting data";
    println("USING PORT: " + port_name);
  } catch (Exception e) {
    println("Serial open failed: " + e.getMessage());
    serial_ready = false;
    serial_status = "open failed";
  }
}

void serialEvent(Serial p) {
  String line = p.readStringUntil('\r');
  parseSerialLine(line);
}

void parseSerialLine(String line) {
  if (line == null) {
    return;
  }

  line = trim(line);
  if (line.length() == 0) {
    return;
  }

  last_serial_line = line;
  String[] parts = splitTokens(line, ",");
  serial_column_count = parts.length;

  if (parts.length == CONTROL_COLUMN_COUNT && parts[0].equals("C")) {
    parseControlLine(parts);
    return;
  }

  if (parts.length == DETAIL_SENSOR_COLUMN_COUNT && parts[0].equals("S")) {
    parseDetailSensorLine(parts);
    return;
  }

  if (parts.length > DETAIL_SENSOR_COLUMN_COUNT) {
    if (tryRecoverTaggedLine(line)) {
      return;
    }
  }

  serial_invalid_count++;
  serial_status = "invalid columns: " + parts.length;
}

void parseControlLine(String[] parts) {
  float new_runtime = parseFloatSafe(parts[1]);
  float new_ax = parseFloatSafe(parts[2]);
  float new_ay = parseFloatSafe(parts[3]);
  float new_shake = parseFloatSafe(parts[4]);
  float new_a = parseFloatSafe(parts[5]);
  float new_b = parseFloatSafe(parts[6]);

  if (!allFinite6(new_runtime, new_ax, new_ay, new_shake, new_a, new_b)) {
    serial_invalid_count++;
    serial_status = "invalid number";
    return;
  }

  if (abs(new_ax) > INPUT_SENSOR_ABS_LIMIT || abs(new_ay) > INPUT_SENSOR_ABS_LIMIT) {
    serial_invalid_count++;
    serial_status = "out of range";
    return;
  }

  int new_btnA_raw = int(constrain(round(new_a), 0, 1));
  int new_btnB_raw = int(constrain(round(new_b), 0, 1));
  int new_shake_raw = int(constrain(round(new_shake), 0, 1));

  if (new_btnA_raw == 1 && btnA_raw == 0) {
    btnA_press_latch = 1;
  }
  if (new_btnB_raw == 1 && btnB_raw == 0) {
    btnB_press_latch = 1;
  }
  if (new_shake_raw == 1 && shake_raw == 0) {
    shake_event_latch = 1;
  }

  microbit_runtime_ms = (long)new_runtime;
  ax_raw = new_ax;
  ay_raw = new_ay;
  shake_raw = new_shake_raw;
  btnA_raw = new_btnA_raw;
  btnB_raw = new_btnB_raw;

  markValidSerialLine("valid control");
}

void parseDetailSensorLine(String[] parts) {
  float new_runtime = parseFloatSafe(parts[1]);
  float new_az = parseFloatSafe(parts[2]);
  float new_light = parseFloatSafe(parts[3]);
  float new_temp = parseFloatSafe(parts[4]);
  float new_pitch = parseFloatSafe(parts[5]);
  float new_roll = parseFloatSafe(parts[6]);

  if (!allFinite6(new_runtime, new_az, new_light, new_temp, new_pitch, new_roll)) {
    serial_invalid_count++;
    serial_status = "invalid number";
    return;
  }

  if (abs(new_az) > INPUT_SENSOR_ABS_LIMIT) {
    serial_invalid_count++;
    serial_status = "out of range";
    return;
  }

  microbit_runtime_ms = (long)new_runtime;
  az_raw = new_az;
  light_raw = (int)new_light;
  temp_raw = (int)new_temp;
  pitch_raw = new_pitch;
  roll_raw = new_roll;

  markValidSerialLine("valid sensor");
}

boolean tryRecoverTaggedLine(String line) {
  String[] lines = splitTokens(line, "\r\n");
  for (int i = lines.length - 1; i >= 0; i--) {
    String candidate = trim(lines[i]);
    if (candidate.length() == 0) {
      continue;
    }

    String[] parts = splitTokens(candidate, ",");
    if (parts.length == CONTROL_COLUMN_COUNT && parts[0].equals("C")) {
      serial_column_count = parts.length;
      last_serial_line = candidate;
      parseControlLine(parts);
      return true;
    }
    if (parts.length == DETAIL_SENSOR_COLUMN_COUNT && parts[0].equals("S")) {
      serial_column_count = parts.length;
      last_serial_line = candidate;
      parseDetailSensorLine(parts);
      return true;
    }
  }
  return false;
}

void markValidSerialLine(String status) {
  if (!has_sensor_data) {
    input_x_smooth = ax_raw;
    input_y_smooth = ay_raw;
    has_sensor_data = true;
  }

  serial_valid = 1;
  serial_valid_count++;
  last_valid_pc_timestamp_ms = System.currentTimeMillis();
  serial_status = status;
}

String findMicrobitPort() {
  String[] ports = Serial.list();
  if (SERIAL_PORT_NAME.length() > 0) {
    return SERIAL_PORT_NAME;
  }

  for (String p : ports) {
    String low = p.toLowerCase();
    if (low.indexOf("usbmodem") >= 0 && low.indexOf("/dev/cu.") >= 0) {
      return p;
    }
  }

  for (String p : ports) {
    String low = p.toLowerCase();
    if (low.indexOf("usbmodem") >= 0 || low.indexOf("microbit") >= 0) {
      return p;
    }
  }

  int best_num = -1;
  String best_port = null;
  for (String p : ports) {
    if (p.startsWith("COM")) {
      int n = parseCOMNumber(p);
      if (n > best_num) {
        best_num = n;
        best_port = p;
      }
    }
  }
  return best_port;
}

int parseCOMNumber(String s) {
  try {
    return int(s.substring(3));
  } catch (Exception e) {
    return -1;
  }
}

float parseFloatSafe(String value) {
  try {
    return float(trim(value));
  } catch (Exception e) {
    return Float.NaN;
  }
}

boolean allFinite6(float a, float b, float c, float d, float e, float f) {
  return isFinite(a) && isFinite(b) && isFinite(c) &&
    isFinite(d) && isFinite(e) && isFinite(f);
}

boolean isFinite(float value) {
  return !Float.isNaN(value) && !Float.isInfinite(value);
}

PFont createPlatformFont(int size) {
  String os = System.getProperty("os.name").toLowerCase();

  if (os.indexOf("mac") >= 0) {
    try {
      return createFont("Hiragino Sans", size, true);
    } catch (Exception e) {
    }
  }

  if (os.indexOf("win") >= 0) {
    try {
      return createFont("Meiryo UI", size, true);
    } catch (Exception e) {
    }
  }

  return createFont("SansSerif", size, true);
}

void stop() {
  closeLog();
  super.stop();
}
