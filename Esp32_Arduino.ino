#include <WiFi.h>
#include <FirebaseESP32.h>
#include <TinyGPS++.h>
#include <HardwareSerial.h>
#include "DHT.h"

// WiFi Credentials
#define WIFI_SSID "HackTU 6.0"
#define WIFI_PASSWORD "ccs#2025"

// Firebase Credentials
#define FIREBASE_HOST "iot-bin-ba8a5-default-rtdb.firebaseio.com"
#define FIREBASE_AUTH "szhfDJBCAIhAconNvxdzxdU1K1tY0Se95Sox0IZO"

// Firebase instance
FirebaseData fbdo;
FirebaseAuth auth;
FirebaseConfig config;

// DHT11 Sensor
#define DPIN 15  
#define DTYPE DHT11
DHT dht(DPIN, DTYPE);

// Tilt Sensor
#define TILT_SENSOR_PIN 21  

// GPS Module
#define RXD2 16  // GPS TX to ESP32 RX2
#define TXD2 17  // GPS RX to ESP32 TX2
TinyGPSPlus gps;
HardwareSerial gpsSerial(1);

// Ultrasonic Sensor HC-SR04
#define TRIG_PIN 4  // Trigger Pin
#define ECHO_PIN 5  // Echo Pin

void setup() {
    Serial.begin(115200);
    gpsSerial.begin(9600, SERIAL_8N1, RXD2, TXD2);

    // Connect to WiFi
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    Serial.print("Connecting to WiFi...");
    while (WiFi.status() != WL_CONNECTED) {
        Serial.print(".");
        delay(1000);
    }
    Serial.println("\nConnected to WiFi!");

    // Firebase Setup
    config.host = FIREBASE_HOST;
    config.signer.tokens.legacy_token = FIREBASE_AUTH;
    Firebase.begin(&config, &auth);
    Firebase.reconnectWiFi(true);

    // Initialize Sensors
    dht.begin();
    pinMode(TILT_SENSOR_PIN, INPUT_PULLDOWN);
    pinMode(TRIG_PIN, OUTPUT);
    pinMode(ECHO_PIN, INPUT);
}

float measureDistance() {
    digitalWrite(TRIG_PIN, LOW);
    delayMicroseconds(2);
    digitalWrite(TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);

    long duration = pulseIn(ECHO_PIN, HIGH);
    float distance = (duration * 0.0343) / 2;  // Convert to cm
    return distance;
}

void loop() {
    // Read Sensors
    float tempC = dht.readTemperature(false);
    float humidity = dht.readHumidity();
    int tiltState = digitalRead(TILT_SENSOR_PIN);
    String tiltStatus = (tiltState == HIGH) ? "Tilt detected!" : "No tilt detected";
    float distance = measureDistance();

    // Read GPS
    float lat = 0.0, lon = 0.0;
    while (gpsSerial.available()) {
        gps.encode(gpsSerial.read());
        if (gps.location.isUpdated()) {
            lat = gps.location.lat();
            lon = gps.location.lng();
        }
    }

    Serial.printf("Temp: %.2f C | Hum: %.2f%% | Tilt: %s | Distance: %.2f cm | GPS: %.6f, %.6f\n",
                  tempC, humidity, tiltStatus.c_str(), distance, lat, lon);

    // Store Live Data in Firebase
    Firebase.setFloat(fbdo, "/LiveData/Temperature_C", tempC);
    Firebase.setFloat(fbdo, "/LiveData/Humidity", humidity);
    Firebase.setString(fbdo, "/LiveData/Tilt", tiltStatus);
    Firebase.setFloat(fbdo, "/LiveData/Distance_cm", distance);
    Firebase.setFloat(fbdo, "/LiveData/GPS/Latitude", lat);
    Firebase.setFloat(fbdo, "/LiveData/GPS/Longitude", lon);

    // Tilt Notification
    if (tiltState == HIGH) {
        Firebase.setBool(fbdo, "/Notifications/TiltAlert", true);
    }

    delay(5000);
}
