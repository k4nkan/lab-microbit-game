final int SCREEN_W = 800;
final int SCREEN_H = 600;
final int GAME_W = 600;
final int DEBUG_X = 620;
final int FRAME_RATE = 60;
final int SERIAL_BAUD = 115200;
final int CONTROL_COLUMN_COUNT = 9;
final int LEGACY_CONTROL_COLUMN_COUNT = 7;
final int DETAIL_SENSOR_COLUMN_COUNT = 7;
final int LOG_FLUSH_EVERY_FRAMES = 30;
final String SERIAL_PORT_NAME = "";

final float PLAYER_W = 48;
final float PLAYER_H = 18;
final float PLAYER_Y = 550;
final float INPUT_DEAD = 3;
final float INPUT_MAX_SPEED = 16;
final float INPUT_SENSOR_ABS_LIMIT = 1400;
final float INPUT_TILT_ABS_LIMIT = 180;
final float INPUT_MAX_SMOOTH_STEP = 8;
final float INPUT_VELOCITY_ALPHA = 0.30;
final float INPUT_AXIS_MAX = 45.0;
final float INPUT_Y_SPEED_SIGN = -1.0;
final float INPUT_SMOOTH_ALPHA = 0.28;
final int INPUT_CALIBRATION_SAMPLES = 60;
final int INPUT_AXIS_STALE_MS = 500;
final int INPUT_BUTTON_STALE_MS = 220;

final float BULLET_R = 5;
final float BULLET_SPEED = 9.0;
final float TARGET_R = 18;
final float TARGET_MIN_SPEED = 1.5;
final float TARGET_MAX_SPEED = 2.8;
final float BOMB_PUSHBACK = 75;
final int BOMB_COOLDOWN_FRAMES = 30;
final int SHOT_BUFFER_FRAMES = 10;
final int LIGHT_SHIELD_THRESHOLD = 35;

Serial serial_port;
boolean serial_ready = false;
boolean has_sensor_data = false;
int serial_valid = 0;
int serial_column_count = 0;
int serial_valid_count = 0;
int serial_invalid_count = 0;
long last_valid_pc_timestamp_ms = 0;
long last_control_pc_timestamp_ms = 0;
String serial_status = "not connected";
String last_serial_line = "";
PFont ui_font;

long microbit_runtime_ms = 0;
float ax_raw = 0;
float ay_raw = 0;
float az_raw = 0;
int light_raw = 255;
int temp_raw = 0;
int shake_raw = 0;
float pitch_raw = 0;
float roll_raw = 0;
int btnA_raw = 0;
int btnB_raw = 0;

boolean input_calibrated = false;
int input_calibration_count = 0;
float input_calibration_x_sum = 0;
float input_calibration_y_sum = 0;
float input_x_neutral = 0;
float input_y_neutral = 0;
float control_x_raw = 0;
float control_y_raw = 0;
float input_x_smooth = 0;
float input_y_smooth = 0;
float tilt_x = 0;
float speed_modifier = 1.0;
int btnA_pressed = 0;
int btnB_pressed = 0;
int shake_event = 0;
int light_shield = 0;
int light_shield_started = 0;

int btnA_press_latch = 0;
int btnB_press_latch = 0;
int shake_event_latch = 0;
int prev_light_shield = 0;
int shot_buffer_frames = 0;

float player_x = 0;
float player_y = PLAYER_Y;
float player_vx = 0;

String target_type = "enemy";
float target_x = 0;
float target_y = 0;
float target_speed = 2;
float target_dx = 0;
float target_dy = 0;
float target_distance = 0;

boolean bullet_active = false;
float bullet_x = 0;
float bullet_y = 0;

int score = 0;
int miss_count = 0;
boolean shield_active = false;
String event_type = "none";
String event_value = "";
boolean target_spawn_pending = false;
int bomb_cooldown_frames = 0;

PrintWriter input_log_writer;
PrintWriter game_log_writer;
String session_id = "";
String input_log_path = "";
String game_log_path = "";
long start_pc_timestamp_ms = 0;
int input_rows_since_flush = 0;
int game_rows_since_flush = 0;
