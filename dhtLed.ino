/*
 * A7 - DHT11 & LED Dashboard dengan MQTT
 * Program Arduino untuk:
 * 1. Membaca sensor DHT11 (suhu dan kelembaban) dan publish via MQTT
 * 2. Menerima perintah via MQTT untuk menyala/matikan LED
 * 
 * Library yang digunakan:
 * - WiFi.h (built-in Arduino/ESP32)
 * - PubSubClient (MQTT Client)
 * - DHT sensor library (Adafruit)
 */

#include <WiFi.h>
#include "PubSubClient.h"
#include "DHT.h"

// ===== KONFIGURASI WIFI =====
const char* ssid = "Adhyasta";           // Ganti dengan nama WiFi Anda
const char* password = "juarasatu";   // Ganti dengan password WiFi Anda

// ===== KONFIGURASI MQTT BROKER =====
const char* mqtt_server = "broker.hivemq.com"; // Atau broker MQTT lain
const int mqtt_port = 1883;

// ===== TOPIK MQTT =====
// GANTI "nama-kelompok/nama" dengan nama kelompok dan nama Anda
const char* topic_publish = "sic/dibimbing/AKUCINTADTETI/heiho/pub/dht";
// const char* topic_subscribe = "sic/dibimbing/AKUCINTADTETI/heiho/sub/led";  // LED belum terpasang

// ===== KONFIGURASI DHT11 =====
#define DHTPIN 4           // Pin data DHT11 (GPIO4 untuk ESP32, pin 4 untuk Arduino)
#define DHTTYPE DHT11      // Tipe sensor DHT11
DHT dht(DHTPIN, DHTTYPE);

// ===== KONFIGURASI LED =====
// #define LED_PIN 2          // Pin LED (GPIO2 untuk ESP32, pin 2 untuk Arduino) - LED belum terpasang

// ===== OBJEK WIFI DAN MQTT =====
WiFiClient wifiClient;
PubSubClient client(wifiClient);

// ===== VARIABEL GLOBAL =====
unsigned long lastPublish = 0;
const long publishInterval = 5000;  // Publish setiap 5 detik

// ===== FUNGSI SETUP WIFI =====
void setup_wifi() {
  delay(10);
  Serial.println();
  Serial.print("Menghubungkan ke WiFi: ");
  Serial.println(ssid);

  // Memulai koneksi WiFi
  WiFi.mode(WIFI_STA);  // Set WiFi mode ke Station (client)
  WiFi.begin(ssid, password);

  // Tunggu sampai terhubung
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  // Generate random seed untuk client ID
  randomSeed(micros());

  Serial.println();
  Serial.println("WiFi terhubung!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
}

// ===== CALLBACK MQTT (Menerima Pesan) =====
// Fungsi callback untuk LED - saat ini di-comment karena LED belum terpasang
/*
void callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Pesan diterima pada topik: ");
  Serial.println(topic);
  
  // Konversi payload ke string
  String message = "";
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  
  Serial.print("Pesan: ");
  Serial.println(message);

  // Kontrol LED berdasarkan pesan
  if (String(topic) == topic_subscribe) {
    if (message == "ON" || message == "1") {
      digitalWrite(LED_PIN, HIGH);
      Serial.println("LED NYALA");
    } 
    else if (message == "OFF" || message == "0") {
      digitalWrite(LED_PIN, LOW);
      Serial.println("LED MATI");
    }
  }
}
*/

// ===== FUNGSI RECONNECT MQTT =====
void reconnect() {
  // Loop sampai terhubung
  while (!client.connected()) {
    Serial.print("Menghubungkan ke MQTT Broker...");
    
    // Buat client ID unik
    String clientId = "ESP8266Client-";
    clientId += String(random(0xffff), HEX);
    
    // Coba hubungkan
    if (client.connect(clientId.c_str())) {
      Serial.println("Terhubung!");
      
      // Subscribe ke topik LED - di-comment karena LED belum terpasang
      // client.subscribe(topic_subscribe);
      // Serial.print("Subscribe ke topik: ");
      // Serial.println(topic_subscribe);
    } 
    else {
      Serial.print("Gagal, rc=");
      Serial.print(client.state());
      Serial.println(" Coba lagi dalam 5 detik...");
      delay(5000);
    }
  }
}

// ===== SETUP =====
void setup() {
  // Inisialisasi Serial Monitor
  Serial.begin(115200);
  
  // Inisialisasi pin LED - di-comment karena LED belum terpasang
  // pinMode(LED_PIN, OUTPUT);
  // digitalWrite(LED_PIN, LOW);
  
  // Inisialisasi DHT11
  dht.begin();
  
  // Setup WiFi
  setup_wifi();
  
  // Setup MQTT
  client.setServer(mqtt_server, mqtt_port);
  // client.setCallback(callback);  // Callback LED di-comment karena LED belum terpasang
  
  Serial.println("===== DHT11 & LED Dashboard Ready =====");
}

// ===== LOOP =====
void loop() {
  // Pastikan terhubung ke MQTT
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  // Publish data DHT11 secara periodik
  unsigned long now = millis();
  if (now - lastPublish > publishInterval) {
    lastPublish = now;
    
    // Baca sensor DHT11
    float humidity = dht.readHumidity();
    float temperature = dht.readTemperature();
    
    // Cek apakah pembacaan valid
    if (isnan(humidity) || isnan(temperature)) {
      Serial.println("Gagal membaca sensor DHT11!");
      return;
    }
    
    // Buat payload JSON
    String payload = "{\"temperature\":";
    payload += String(temperature, 1);
    payload += ",\"humidity\":";
    payload += String(humidity, 1);
    payload += "}";
    
    // Publish ke MQTT
    if (client.publish(topic_publish, payload.c_str())) {
      Serial.println("Data dipublikasikan:");
      Serial.print("  Topik: ");
      Serial.println(topic_publish);
      Serial.print("  Payload: ");
      Serial.println(payload);
      Serial.print("  Suhu: ");
      Serial.print(temperature);
      Serial.println(" °C");
      Serial.print("  Kelembaban: ");
      Serial.print(humidity);
      Serial.println(" %");
    } 
    else {
      Serial.println("Gagal publish data!");
    }
  }
}
