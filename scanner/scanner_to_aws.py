import ssl
import time
import json  # ⭐ JSON 변환을 위해 추가
import paho.mqtt.client as mqtt

AWS_IOT_ENDPOINT = "a3nk4hs9r81jqn-ats.iot.us-east-2.amazonaws.com"
AWS_IOT_PORT = 8883
ROOT_CA = "root-CA.crt"
CERTIFICATE = "SR160-scanner.cert.pem"
PRIVATE_KEY = "SR160-scanner.private.key"
MQTT_TOPIC = "sr160/scanned"

# --- MQTT 연결 성공 시 콜백 함수 ---
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[MQTT] Connected successfully to AWS IoT Core!")
    else:
        print(f"[MQTT] Connection failed with code {rc}")

# --- MQTT 클라이언트 생성 및 설정 ---
mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect  # 연결 성공 콜백 등록

mqtt_client.tls_set(
    ca_certs=ROOT_CA,
    certfile=CERTIFICATE,
    keyfile=PRIVATE_KEY,
    tls_version=ssl.PROTOCOL_TLSv1_2
)

print("[MQTT] Connecting to AWS IoT Core...")
mqtt_client.connect(AWS_IOT_ENDPOINT, AWS_IOT_PORT, 60)
mqtt_client.loop_start()  # 🔥 MQTT 패킷 백그라운드 처리

print("Ready to manually type scan data. (Ctrl+C to stop)")

# --- 데이터 입력 및 발행 ---
try:
    while True:
        scanned_text = input("Type scan data: ")

        # ⭐ 입력한 텍스트를 JSON으로 변환
        payload = json.dumps({"scanData": scanned_text})

        print(f"[Publishing] {payload}")
        result = mqtt_client.publish(MQTT_TOPIC, payload=payload, qos=1)
        status = result.rc
        if status == 0:
            print(f"[MQTT] Message sent to topic {MQTT_TOPIC}")
        else:
            print(f"[MQTT] Failed to send message to topic {MQTT_TOPIC}, status={status}")
except KeyboardInterrupt:
    print("Stopped by user.")
finally:
    mqtt_client.loop_stop()
    mqtt_client.disconnect()


#import keyboard
#import ssl
#import time
#import paho.mqtt.client as mqtt
#
## --- AWS IoT Core 설정 ---
#AWS_IOT_ENDPOINT = "a3nk4hs9r81jqn-ats.iot.us-east-2.amazonaws.com"
#AWS_IOT_PORT = 8883
#ROOT_CA = "root-CA.crt"                  # 이거 곧 다운로드할 거예요
#CERTIFICATE = "SR160-scanner.cert.pem"
#PRIVATE_KEY = "SR160-scanner.private.key"
#MQTT_TOPIC = "sr160/scanned"
#
## --- MQTT 클라이언트 생성 ---
#mqtt_client = mqtt.Client()
#
#mqtt_client.tls_set(
#    ca_certs=ROOT_CA,
#    certfile=CERTIFICATE,
#    keyfile=PRIVATE_KEY,
#    tls_version=ssl.PROTOCOL_TLSv1_2
#)
#
#mqtt_client.connect(AWS_IOT_ENDPOINT, AWS_IOT_PORT, 60)
#
## --- 스캔 데이터 수집 함수 ---
#def listen_for_scan():
#    print("Ready to scan... (Press Ctrl+C to stop)")
#
#    scanned_text = ""
#    while True:
#        event = keyboard.read_event()
#        if event.event_type == keyboard.KEY_DOWN:
#            if event.name == 'enter':
#                print(f"[SCANNED] {scanned_text}")
#
#                # 스캔 결과를 AWS IoT Core로 Publish
#                mqtt_client.publish(MQTT_TOPIC, payload=scanned_text, qos=1)
#                scanned_text = ""
#            else:
#                if len(event.name) == 1:
#                    scanned_text += event.name
#                elif event.name == "space":
#                    scanned_text += " "
#
#try:
#    listen_for_scan()
#except KeyboardInterrupt:
#    print("Stopped by user.")
#finally:
#    mqtt_client.disconnect()
