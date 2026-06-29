#include <Arduino.h>

const uint8_t HEADER = 0xA5;
const size_t PACKET_SIZE = 12;

struct ViolinEvent {
  uint16_t tick;
  uint8_t pitch;
  uint16_t duration;
  uint8_t stringId;
  uint8_t finger;
  uint8_t position;
  uint8_t bowDirection;
  uint8_t bowSpeed;
  uint8_t bowForce;
  uint8_t flags;
};

bool decodePacket(const uint8_t *packet, ViolinEvent &event) {
  if (packet[0] != HEADER) {
    return false;
  }

  uint8_t checksum = 0;
  for (size_t i = 0; i < 11; ++i) {
    checksum += packet[i];
  }
  if (checksum != packet[11]) {
    return false;
  }

  event.tick = packet[1] | (packet[2] << 8);
  event.pitch = packet[3];
  event.duration = packet[4] | (packet[5] << 8);
  event.stringId = (packet[6] >> 6) & 0x03;
  event.finger = (packet[6] >> 3) & 0x07;
  event.position = packet[6] & 0x07;
  event.bowDirection = (packet[7] >> 7) & 0x01;
  event.bowSpeed = packet[7] & 0x7F;
  event.bowForce = packet[8];
  event.flags = packet[9];
  return true;
}

void sendAck(const ViolinEvent &event) {
  Serial.print("ACK tick=");
  Serial.print(event.tick);
  Serial.print(" pitch=");
  Serial.print(event.pitch);
  Serial.print(" string=");
  Serial.print(event.stringId);
  Serial.print(" finger=");
  Serial.print(event.finger);
  Serial.print(" position=");
  Serial.println(event.position);
}

void setup() {
  Serial.begin(115200);
  while (!Serial) {
  }
  Serial.println("READY giga_serial_bridge");
}

void loop() {
  static uint8_t packet[PACKET_SIZE];
  static size_t index = 0;

  while (Serial.available() > 0) {
    uint8_t value = Serial.read();

    if (index == 0 && value != HEADER) {
      continue;
    }

    packet[index++] = value;
    if (index < PACKET_SIZE) {
      continue;
    }

    ViolinEvent event;
    if (decodePacket(packet, event)) {
      sendAck(event);
      // Future integration point: playEvent(event);
    } else {
      Serial.println("NACK invalid_packet");
    }
    index = 0;
  }
}
