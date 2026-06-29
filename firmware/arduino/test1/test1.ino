#include "littlestar.h"

const uint8_t HEADER = 0xA5;
const int PACKET_SIZE = 12;

struct ViolinEvent {
  uint16_t tick;
  uint8_t pitch;
  uint16_t duration;
  uint8_t string_id;
  uint8_t finger;
  uint8_t position;
  uint8_t bow_direction;
  uint8_t bow_speed;
  uint8_t bow_force;
  uint8_t flags;
};

bool decodePacket(const uint8_t *buf, ViolinEvent &evt) {
  if (buf[0] != HEADER) return false;

  uint8_t sum = 0;
  for (int i = 0; i < 11; i++) {
    sum += buf[i];
  }
  if (sum != buf[11]) return false;

  evt.tick = buf[1] | (buf[2] << 8);
  evt.pitch = buf[3];
  evt.duration = buf[4] | (buf[5] << 8);

  evt.string_id = (buf[6] >> 6) & 0x03;
  evt.finger = (buf[6] >> 3) & 0x07;
  evt.position = buf[6] & 0x07;

  evt.bow_direction = (buf[7] >> 7) & 0x01;
  evt.bow_speed = buf[7] & 0x7F;
  evt.bow_force = buf[8];
  evt.flags = buf[9];

  return true;
}

void printEvent(const ViolinEvent &evt) {
  Serial.print("OK tick=");
  Serial.print(evt.tick);
  Serial.print(" pitch=");
  Serial.print(evt.pitch);
  Serial.print(" duration=");
  Serial.print(evt.duration);
  Serial.print(" string=");
  Serial.print(evt.string_id);
  Serial.print(" finger=");
  Serial.print(evt.finger);
  Serial.print(" position=");
  Serial.print(evt.position);
  Serial.print(" bow_dir=");
  Serial.print(evt.bow_direction);
  Serial.print(" bow_speed=");
  Serial.print(evt.bow_speed);
  Serial.print(" bow_force=");
  Serial.println(evt.bow_force);
}

void setup() {
  Serial.begin(115200);
  while (!Serial) {}

  Serial.println("Start decoding score...");

  for (unsigned int i = 0; i < twinkle_score_len; i += PACKET_SIZE) {
    ViolinEvent evt;

    if (decodePacket(&twinkle_score[i], evt)) {
      printEvent(evt);
    } else {
      Serial.print("BAD PACKET at byte ");
      Serial.println(i);
    }
  }

  Serial.println("Done.");
}

void loop() {
}