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
  String[] parts = split(line, ',');
  serial_column_count = parts.length;

  if (parseTaggedParts(parts)) {
    return;
  }

  if (tryRecoverTaggedLine(line)) {
    return;
  }

  serial_invalid_count++;
  serial_status = "invalid columns: " + parts.length;
}

boolean parseTaggedParts(String[] parts) {
  if (isControlLine(parts)) {
    parseControlLine(parts);
    return true;
  }

  if (isLegacyControlLine(parts)) {
    parseLegacyControlLine(parts);
    return true;
  }

  if (isDetailSensorLine(parts)) {
    parseDetailSensorLine(parts);
    return true;
  }

  return false;
}

boolean isControlLine(String[] parts) {
  return parts.length == CONTROL_COLUMN_COUNT && parts[0].equals("C");
}

boolean isLegacyControlLine(String[] parts) {
  return parts.length == LEGACY_CONTROL_COLUMN_COUNT && parts[0].equals("C");
}

boolean isDetailSensorLine(String[] parts) {
  return parts.length == DETAIL_SENSOR_COLUMN_COUNT && parts[0].equals("S");
}

void parseControlLine(String[] parts) {
  float new_runtime = parseFloatSafe(parts[1]);
  float new_ax = parseFloatSafe(parts[2]);
  float new_ay = parseFloatSafe(parts[3]);
  float new_roll = parseFloatSafe(parts[4]);
  float new_pitch = parseFloatSafe(parts[5]);
  float new_shake = parseFloatSafe(parts[6]);
  float new_a = parseFloatSafe(parts[7]);
  float new_b = parseFloatSafe(parts[8]);

  if (!allFinite8(new_runtime, new_ax, new_ay, new_roll, new_pitch,
      new_shake, new_a, new_b)) {
    markInvalidSerialLine("invalid number");
    return;
  }

  if (abs(new_ax) > INPUT_SENSOR_ABS_LIMIT || abs(new_ay) > INPUT_SENSOR_ABS_LIMIT ||
      abs(new_roll) > INPUT_TILT_ABS_LIMIT || abs(new_pitch) > INPUT_TILT_ABS_LIMIT) {
    markInvalidSerialLine("out of range");
    return;
  }

  if (!isBinaryValue(new_shake) || !isBinaryValue(new_a) || !isBinaryValue(new_b)) {
    markInvalidSerialLine("invalid button");
    return;
  }

  roll_raw = new_roll;
  pitch_raw = new_pitch;
  applyControlInput(new_runtime, new_ax, new_ay, new_roll, new_pitch,
    new_shake, new_a, new_b, "valid control");
}

void parseLegacyControlLine(String[] parts) {
  float new_runtime = parseFloatSafe(parts[1]);
  float new_ax = parseFloatSafe(parts[2]);
  float new_ay = parseFloatSafe(parts[3]);
  float new_shake = parseFloatSafe(parts[4]);
  float new_a = parseFloatSafe(parts[5]);
  float new_b = parseFloatSafe(parts[6]);

  if (!allFinite6(new_runtime, new_ax, new_ay, new_shake, new_a, new_b)) {
    markInvalidSerialLine("invalid number");
    return;
  }

  if (abs(new_ax) > INPUT_SENSOR_ABS_LIMIT || abs(new_ay) > INPUT_SENSOR_ABS_LIMIT) {
    markInvalidSerialLine("out of range");
    return;
  }

  if (!isBinaryValue(new_shake) || !isBinaryValue(new_a) || !isBinaryValue(new_b)) {
    markInvalidSerialLine("invalid button");
    return;
  }

  applyControlInput(new_runtime, new_ax, new_ay,
    accelerationToTiltDegrees(new_ax), accelerationToTiltDegrees(new_ay),
    new_shake, new_a, new_b, "valid control");
}

void applyControlInput(float new_runtime, float new_ax, float new_ay,
    float new_control_x, float new_control_y,
    float new_shake, float new_a, float new_b, String status) {
  int new_shake_raw = int(new_shake);
  int new_btnA_raw = int(new_a);
  int new_btnB_raw = int(new_b);

  updateButtonLatches(new_btnA_raw, new_btnB_raw, new_shake_raw);

  microbit_runtime_ms = (long)new_runtime;
  ax_raw = new_ax;
  ay_raw = new_ay;
  control_x_raw = new_control_x;
  control_y_raw = new_control_y;
  shake_raw = new_shake_raw;
  btnA_raw = new_btnA_raw;
  btnB_raw = new_btnB_raw;
  updateInputCalibration(control_x_raw, control_y_raw);
  last_control_pc_timestamp_ms = System.currentTimeMillis();

  markValidSerialLine(status);
}

void updateButtonLatches(int new_btnA_raw, int new_btnB_raw, int new_shake_raw) {
  if (new_btnA_raw == 1 && btnA_raw == 0) {
    btnA_press_latch = 1;
  }
  if (new_btnB_raw == 1 && btnB_raw == 0) {
    btnB_press_latch = 1;
  }
  if (new_shake_raw == 1 && shake_raw == 0) {
    shake_event_latch = 1;
  }
}

void parseDetailSensorLine(String[] parts) {
  float new_runtime = parseFloatSafe(parts[1]);
  float new_az = parseFloatSafe(parts[2]);
  float new_light = parseFloatSafe(parts[3]);
  float new_temp = parseFloatSafe(parts[4]);
  float new_pitch = parseFloatSafe(parts[5]);
  float new_roll = parseFloatSafe(parts[6]);

  if (!allFinite6(new_runtime, new_az, new_light, new_temp, new_pitch, new_roll)) {
    markInvalidSerialLine("invalid number");
    return;
  }

  if (abs(new_az) > INPUT_SENSOR_ABS_LIMIT) {
    markInvalidSerialLine("out of range");
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

    String[] parts = split(candidate, ',');
    if (parseTaggedParts(parts)) {
      serial_column_count = parts.length;
      last_serial_line = candidate;
      return true;
    }
  }
  return false;
}

void markValidSerialLine(String status) {
  if (!has_sensor_data) {
    has_sensor_data = true;
  }

  serial_valid = 1;
  serial_valid_count++;
  last_valid_pc_timestamp_ms = System.currentTimeMillis();
  serial_status = status;
}

void markInvalidSerialLine(String status) {
  serial_invalid_count++;
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

boolean allFinite8(float a, float b, float c, float d, float e,
    float f, float g, float h) {
  return isFinite(a) && isFinite(b) && isFinite(c) &&
    isFinite(d) && isFinite(e) && isFinite(f) &&
    isFinite(g) && isFinite(h);
}

boolean isBinaryValue(float value) {
  return value == 0 || value == 1;
}

float accelerationToTiltDegrees(float acceleration) {
  float ratio = constrain(acceleration / 1024.0, -1.0, 1.0);
  return degrees(asin(ratio));
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
