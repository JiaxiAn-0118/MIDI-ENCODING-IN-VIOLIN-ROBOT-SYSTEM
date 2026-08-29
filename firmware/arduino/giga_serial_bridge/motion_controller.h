#ifndef VIOLIN_MOTION_CONTROLLER_H
#define VIOLIN_MOTION_CONTROLLER_H

#include "protocol.h"
#include "drivers.h"

/*
 * ============================================================================
 *  动作状态机与调度层 (Motion Controller Layer)
 * ============================================================================
 *  负责解析后的 ViolinEvent 与各硬件驱动之间的协调与状态管理。
 *  处理双手协同（左手按弦提前量、换弦倾角对齐、运弓连奏逻辑等）。
 * ============================================================================
 */

class MotionController {
private:
  IBowDriver &bowDriver;
  IStringDriver &stringDriver;
  IFingerDriver &fingerDriver;
  IPressureDriver &pressureDriver;

  bool previousLegato = false;
  uint8_t currentBowDir = 0;
  uint8_t currentStringId = 255;

public:
  MotionController(IBowDriver &bow, IStringDriver &str, IFingerDriver &fng, IPressureDriver &prs)
    : bowDriver(bow), stringDriver(str), fingerDriver(fng), pressureDriver(prs) {}

  void init() {
    bowDriver.init();
    stringDriver.init();
    fingerDriver.init();
    pressureDriver.init();
    Serial.println("[MotionController] All sub-systems ready");
  }

  // 执行一个演奏事件
  void executeEvent(const ViolinEvent &event) {
    bool isLegato = event.isLegato();

    // 1. 左手按弦动作 (按弦/换把)
    fingerDriver.press(event.stringId, event.finger, event.position);

    // 2. 换弦动作 (如果换了弦，调整仰角)
    if (event.stringId != currentStringId) {
      stringDriver.selectString(event.stringId);
      currentStringId = event.stringId;
    }

    // 3. 弓压设定
    pressureDriver.setPressure(event.bowForce);

    // 4. 运弓决策 (连奏判断)
    if (isLegato && previousLegato) {
      // 连奏继续：保持原弓向，更新弓速与压力
      Serial.println("[MotionController] >>> Legato continuous stroke");
      bowDriver.setDirectionAndSpeed(currentBowDir, event.bowSpeed);
    } else {
      // 新弓段或断奏：切换/重设弓向与速度
      currentBowDir = event.bowDirection;
      Serial.println("[MotionController] >>> New bow stroke started");
      bowDriver.setDirectionAndSpeed(currentBowDir, event.bowSpeed);
    }

    previousLegato = isLegato;
  }

  void emergencyStop() {
    bowDriver.stop();
    fingerDriver.releaseAll();
    previousLegato = false;
    Serial.println("[MotionController] EMERGENCY STOP TRIGGERED");
  }
};

#endif // VIOLIN_MOTION_CONTROLLER_H
