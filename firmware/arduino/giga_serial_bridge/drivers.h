#ifndef VIOLIN_DRIVERS_H
#define VIOLIN_DRIVERS_H

#include <Arduino.h>

/*
 * ============================================================================
 *  硬件抽象层 (Driver / HAL Layer)
 * ============================================================================
 *  定义小提琴执行机构的抽象接口 (Interface)。
 *  当前硬件未加工完成时，使用 MockDrivers 进行纯软件串口打印仿真；
 *  硬件到位后，只需继承接口并实现对应的电机/舵机/电磁铁控制即可无缝切换。
 * ============================================================================
 */

// 1. 运弓直线滑台接口
class IBowDriver {
public:
  virtual ~IBowDriver() = default;
  virtual void init() = 0;
  virtual void setDirectionAndSpeed(uint8_t direction, uint8_t speed) = 0;
  virtual void stop() = 0;
};

// 2. 换弦仰角控制接口 (双连杆/倾角舵机)
class IStringDriver {
public:
  virtual ~IStringDriver() = default;
  virtual void init() = 0;
  virtual void selectString(uint8_t stringId) = 0; // 0=G, 1=D, 2=A, 3=E
};

// 3. 左手按弦与把位接口
class IFingerDriver {
public:
  virtual ~IFingerDriver() = default;
  virtual void init() = 0;
  virtual void press(uint8_t stringId, uint8_t finger, uint8_t position) = 0;
  virtual void releaseAll() = 0;
};

// 4. 弓压控制接口 (压力电磁/伺服)
class IPressureDriver {
public:
  virtual ~IPressureDriver() = default;
  virtual void init() = 0;
  virtual void setPressure(uint8_t force) = 0;
};

// ============================================================================
//  Mock 仿真实现 (用于无硬件阶段的联调与测试)
// ============================================================================

class MockBowDriver : public IBowDriver {
private:
  uint8_t currentDir = 0;
  uint8_t currentSpeed = 0;

public:
  void init() override {
    Serial.println("[Driver:Bow] Initialized (Mock)");
  }

  void setDirectionAndSpeed(uint8_t direction, uint8_t speed) override {
    currentDir = direction;
    currentSpeed = speed;
    Serial.print("[Driver:Bow] Dir=");
    Serial.print(direction == 0 ? "PULL(拉)" : "PUSH(推)");
    Serial.print(" | Speed=");
    Serial.println(speed);
  }

  void stop() override {
    currentSpeed = 0;
    Serial.println("[Driver:Bow] Stopped");
  }
};

class MockStringDriver : public IStringDriver {
private:
  const char* stringNames[4] = {"G弦(4)", "D弦(3)", "A弦(2)", "E弦(1)"};
  uint8_t currentString = 2; // 默认 A 弦

public:
  void init() override {
    Serial.println("[Driver:String] Initialized (Mock)");
  }

  void selectString(uint8_t stringId) override {
    if (stringId < 4) {
      currentString = stringId;
      Serial.print("[Driver:String] Tilt to -> ");
      Serial.println(stringNames[stringId]);
    }
  }
};

class MockFingerDriver : public IFingerDriver {
private:
  const char* fingerNames[5] = {"空弦", "1指(食)", "2指(中)", "3指(无名)", "4指(小)"};

public:
  void init() override {
    Serial.println("[Driver:Finger] Initialized (Mock)");
  }

  void press(uint8_t stringId, uint8_t finger, uint8_t position) override {
    if (finger == 0) {
      Serial.print("[Driver:Finger] Open string (无按压) on string ");
      Serial.println(stringId);
    } else {
      Serial.print("[Driver:Finger] Press String=");
      Serial.print(stringId);
      Serial.print(" | Finger=");
      Serial.print(fingerNames[finger > 4 ? 0 : finger]);
      Serial.print(" | Position=第");
      Serial.print(position);
      Serial.println("把位");
    }
  }

  void releaseAll() override {
    Serial.println("[Driver:Finger] Released all fingers");
  }
};

class MockPressureDriver : public IPressureDriver {
private:
  uint8_t currentForce = 0;

public:
  void init() override {
    Serial.println("[Driver:Pressure] Initialized (Mock)");
  }

  void setPressure(uint8_t force) override {
    currentForce = force;
    Serial.print("[Driver:Pressure] Force=");
    Serial.println(force);
  }
};

#endif // VIOLIN_DRIVERS_H
