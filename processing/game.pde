void processInput() {
  if (has_sensor_data) {
    input_x_smooth = smoothSensorValue(input_x_smooth, ax_raw);
    input_y_smooth = smoothSensorValue(input_y_smooth, ay_raw);
  }

  float input_x = input_x_smooth;
  if (abs(input_x) < INPUT_DEAD) {
    input_x = 0;
  }
  tilt_x = constrain(input_x / INPUT_AXIS_MAX, -1.0, 1.0);

  float input_y = constrain((input_y_smooth * INPUT_Y_SPEED_SIGN) / INPUT_AXIS_MAX, -1.0, 1.0);
  speed_modifier = 1.0 + input_y * 0.15;
  speed_modifier = constrain(speed_modifier, 0.85, 1.15);

  btnA_pressed = btnA_press_latch;
  btnB_pressed = btnB_press_latch;
  shake_event = shake_event_latch;
  btnA_press_latch = 0;
  btnB_press_latch = 0;
  shake_event_latch = 0;

  light_shield = (has_sensor_data && light_raw <= LIGHT_SHIELD_THRESHOLD) ? 1 : 0;
  light_shield_started = (light_shield == 1 && prev_light_shield == 0) ? 1 : 0;

  float target_vx = tilt_x * INPUT_MAX_SPEED * speed_modifier;
  player_vx = lerp(player_vx, target_vx, INPUT_VELOCITY_ALPHA);
  player_vx = constrain(player_vx, -INPUT_MAX_SPEED, INPUT_MAX_SPEED);

  prev_light_shield = light_shield;
}

float smoothSensorValue(float current_value, float target_value) {
  float delta = (target_value - current_value) * INPUT_SMOOTH_ALPHA;
  delta = constrain(delta, -INPUT_MAX_SMOOTH_STEP, INPUT_MAX_SMOOTH_STEP);
  return current_value + delta;
}

void updateGame() {
  player_x += player_vx;
  player_x = constrain(player_x, PLAYER_W * 0.5, GAME_W - PLAYER_W * 0.5);
  shield_active = (btnB_raw == 1);

  if (btnB_pressed == 1) {
    setEvent("shield", light_shield == 1 ? "boosted" : "on");
  } else if (light_shield_started == 1) {
    setEvent("shield", "light");
  }

  if (btnA_pressed == 1 && !bullet_active) {
    bullet_active = true;
    bullet_x = player_x;
    bullet_y = player_y - PLAYER_H;
    setEvent("shot", "A");
  }

  if (bomb_cooldown_frames > 0) {
    bomb_cooldown_frames--;
  }

  if (shake_event == 1 && bomb_cooldown_frames == 0) {
    target_y = max(-TARGET_R, target_y - BOMB_PUSHBACK);
    bomb_cooldown_frames = BOMB_COOLDOWN_FRAMES;
    setEvent("bomb", "shake");
  }

  if (bullet_active) {
    bullet_y -= BULLET_SPEED;
    if (bullet_y < -BULLET_R) {
      bullet_active = false;
    }
  }

  target_y += target_speed;
  updateTargetMetrics();

  if (bulletHitsTarget()) {
    score++;
    bullet_active = false;
    spawnTarget();
    updateTargetMetrics();
    forceEvent("hit", "score+1");
  } else if (targetMissed()) {
    miss_count++;
    spawnTarget();
    updateTargetMetrics();
    forceEvent("miss", "miss+1");
  } else if (target_spawn_pending && event_type.equals("none")) {
    setEvent("target_spawn", target_type);
    target_spawn_pending = false;
  }
}

void drawGame() {
  background(18, 24, 32);

  drawPlayField();
  drawPlayer();
  drawBullet();
  drawTarget();
  drawDebugPanel();
}

void drawPlayField() {
  noStroke();
  fill(12, 18, 26);
  rect(0, 0, GAME_W, SCREEN_H);

  stroke(55, 70, 86);
  line(GAME_W, 0, GAME_W, SCREEN_H);

  stroke(36, 50, 64);
  for (int y = 60; y < SCREEN_H; y += 60) {
    line(0, y, GAME_W, y);
  }
}

void drawPlayer() {
  rectMode(CENTER);

  if (shield_active) {
    noFill();
    stroke(light_shield == 1 ? color(90, 220, 255) : color(80, 160, 255));
    strokeWeight(light_shield == 1 ? 4 : 2);
    ellipse(player_x, player_y, PLAYER_W * (light_shield == 1 ? 1.9 : 1.5), 46);
    strokeWeight(1);
  }

  noStroke();
  fill(70, 220, 170);
  rect(player_x, player_y, PLAYER_W, PLAYER_H, 3);
  triangle(player_x - 14, player_y - PLAYER_H * 0.5,
    player_x + 14, player_y - PLAYER_H * 0.5,
    player_x, player_y - PLAYER_H * 1.3);
}

void drawBullet() {
  if (!bullet_active) {
    return;
  }

  noStroke();
  fill(255, 230, 120);
  circle(bullet_x, bullet_y, BULLET_R * 2);
}

void drawTarget() {
  rectMode(CENTER);
  noStroke();
  fill(255, 95, 95);
  rect(target_x, target_y, TARGET_R * 2, TARGET_R * 2, 4);

  fill(12, 18, 26);
  circle(target_x - 7, target_y - 4, 5);
  circle(target_x + 7, target_y - 4, 5);
  rect(target_x, target_y + 8, 18, 4, 1);
}

void drawDebugPanel() {
  noStroke();
  fill(24, 30, 40);
  rectMode(CORNER);
  rect(GAME_W + 1, 0, SCREEN_W - GAME_W - 1, SCREEN_H);

  fill(235);
  textAlign(LEFT, TOP);
  textSize(14);

  int x = DEBUG_X;
  int y = 22;
  int lh = 24;

  text("ax_raw: " + nf(ax_raw, 0, 2), x, y); y += lh;
  text("input_x_smooth: " + nf(input_x_smooth, 0, 2), x, y); y += lh;
  text("ay_raw: " + nf(ay_raw, 0, 2), x, y); y += lh;
  text("input_y_smooth: " + nf(input_y_smooth, 0, 2), x, y); y += lh;
  text("tilt_x: " + nf(tilt_x, 0, 3), x, y); y += lh;
  text("roll_angle: " + nf(roll_raw, 0, 2), x, y); y += lh;
  text("pitch_angle: " + nf(pitch_raw, 0, 2), x, y); y += lh;
  text("btnA_raw: " + btnA_raw, x, y); y += lh;
  text("btnA_pressed: " + btnA_pressed, x, y); y += lh;
  text("btnB_raw: " + btnB_raw, x, y); y += lh;
  text("shake: " + shake_raw, x, y); y += lh;
  text("light: " + light_raw, x, y); y += lh;
  text("temp: " + temp_raw, x, y); y += lh;
  text("az_raw: " + nf(az_raw, 0, 2), x, y); y += lh;
  text("score: " + score, x, y); y += lh;
  text("miss_count: " + miss_count, x, y); y += lh;
  text("event_type: " + event_type, x, y); y += lh * 2;

  fill(has_sensor_data ? color(120, 220, 150) : color(255, 180, 90));
  text("serial: " + serial_status, x, y); y += lh;
  fill(180);
  text("columns: " + serial_column_count, x, y); y += lh;
  text("valid rows: " + serial_valid_count, x, y); y += lh;
  text("last line: " + shortSerialLine(), x, y);
}

void resetGame() {
  player_x = GAME_W * 0.5;
  player_y = PLAYER_Y;
  player_vx = 0;
  bullet_active = false;
  score = 0;
  miss_count = 0;
  shield_active = false;
  bomb_cooldown_frames = 0;
  spawnTarget();
  updateTargetMetrics();
}

void spawnTarget() {
  target_type = "enemy";
  target_x = random(TARGET_R + 12, GAME_W - TARGET_R - 12);
  target_y = -TARGET_R;
  target_speed = random(TARGET_MIN_SPEED, TARGET_MAX_SPEED);
  target_spawn_pending = true;
}

void updateTargetMetrics() {
  target_dx = target_x - player_x;
  target_dy = target_y - player_y;
  target_distance = dist(player_x, player_y, target_x, target_y);
}

boolean bulletHitsTarget() {
  if (!bullet_active) {
    return false;
  }
  return dist(bullet_x, bullet_y, target_x, target_y) <= (BULLET_R + TARGET_R);
}

boolean targetMissed() {
  return target_y - TARGET_R > SCREEN_H;
}

void setEvent(String type, String value) {
  if (event_type.equals("none")) {
    event_type = type;
    event_value = value;
  }
}

void forceEvent(String type, String value) {
  event_type = type;
  event_value = value;
}

String shortSerialLine() {
  if (last_serial_line == null || last_serial_line.length() == 0) {
    return "";
  }
  if (last_serial_line.length() <= 24) {
    return last_serial_line;
  }
  return last_serial_line.substring(0, 24);
}
