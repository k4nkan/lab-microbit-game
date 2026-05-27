let ax = 0;
let ay = 0;
let az = 0;
let lightLevelValue = 0;
let temp = 0;
let shake = 0;
let pitch = 0;
let roll = 0;
let a = 0;
let b = 0;
let runtimeMs = 0;
let lastDetailMs = 0;
let sendDetail = false;

serial.redirectToUSB();
serial.setBaudRate(BaudRate.BaudRate115200);

basic.forever(function () {
  runtimeMs = control.millis();
  ax = input.acceleration(Dimension.X); // 左右傾き
  ay = input.acceleration(Dimension.Y); // 前後傾き
  shake = input.isGesture(Gesture.Shake) ? 1 : 0; // 振ったかどうか
  a = input.buttonIsPressed(Button.A) ? 1 : 0;
  b = input.buttonIsPressed(Button.B) ? 1 : 0;

  // "C,runtime,ax,ay,shake,A,B"
  serial.writeLine(
    "C," + runtimeMs + "," + ax + "," + ay + "," + shake + "," + a + "," + b,
  );

  if (sendDetail && runtimeMs - lastDetailMs >= 2000) {
    lastDetailMs = runtimeMs;
    az = input.acceleration(Dimension.Z); // 上下方向
    lightLevelValue = input.lightLevel(); // 明るさ
    temp = input.temperature(); // 温度
    pitch = input.rotation(Rotation.Pitch); // 前後の角度
    roll = input.rotation(Rotation.Roll); // 左右の角度

    // "S,runtime,az,light,temp,pitch,roll"
    serial.writeLine(
      "S," +
        runtimeMs +
        "," +
        az +
        "," +
        lightLevelValue +
        "," +
        temp +
        "," +
        pitch +
        "," +
        roll,
    );
  }

  basic.pause(50);
});
