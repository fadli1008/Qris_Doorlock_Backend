#include <WiFi.h>
#include <WebServer.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <Bounce2.h>

// === Konfigurasi WiFi ===
const char* ssid = "FRR";
const char* password = "Durengede7";

// === Web Server ===
WebServer server(80);
const int relayPin = 5;     // Pin relay
const int buttonPin = 4;    // Pin push button (GPIO4)

// === LCD I2C ===
LiquidCrystal_I2C lcd(0x27, 16, 2);

// === Tombol debounce dengan Bounce2 ===
Bounce debouncer = Bounce();

// === Variabel status pintu ===
String doorStatus = "PINTU TERTUTUP";

// === Variabel kontrol pintu non-blocking ===
bool doorOpen = false;
unsigned long doorOpenTime = 0;
const unsigned long doorOpenDuration = 5000; // 5 detik
const unsigned long relayPulse = 100;        // delay relay untuk keamanan

// === Variabel ganti tampilan LCD ===
unsigned long lastSwitchTime = 0;
bool showIP = true;

// ================= Fungsi =================

void updateLCDLine(int line, String text) {
  lcd.setCursor(0, line);
  String padded = text;
  while (padded.length() < 16) padded += " "; // pastikan menimpa karakter lama
  lcd.print(padded);
}

void showLCD() {
  if (showIP) {
    updateLCDLine(0, "IP Address:");
    updateLCDLine(1, WiFi.localIP().toString());
  } else {
    updateLCDLine(0, "Status Pintu:");
    updateLCDLine(1, doorStatus);
  }
}

// Fungsi buka pintu (non-blocking)
void bukaPintu(String source = "UNKNOWN") {
  if (doorOpen) {
    Serial.println("Request diabaikan, pintu masih terbuka (" + source + ")");
    return;
  }

  // Aktifkan relay
  digitalWrite(relayPin, LOW);
  delay(relayPulse); // delay kecil untuk keamanan mekanis
  doorStatus = "PINTU TERBUKA";
  Serial.println("Buka Pintu via " + source + " pada " + String(millis()/1000) + " detik");

  doorOpen = true;
  doorOpenTime = millis();
  showLCD();
}

// Fungsi tutup pintu otomatis
void tutupPintu() {
  digitalWrite(relayPin, HIGH);
  delay(relayPulse); // delay kecil untuk keamanan
  doorStatus = "PINTU TERTUTUP";
  Serial.println(doorStatus + " pada " + String(millis()/1000) + " detik");
  doorOpen = false;
  showLCD();
}

// Handler web unlock
void handleUnlock() {
  bukaPintu("WEB/QR");
  String json = "{";
  json += "\"status\":\"PINTU TERBUKA\",";
  json += "\"time\":" + String(millis()/1000);
  json += "}";
  server.send(200, "application/json", json);
}

// ================= Setup =================
void setup() {
  Serial.begin(115200);

  pinMode(relayPin, OUTPUT);
  digitalWrite(relayPin, HIGH); // relay OFF (pintu tertutup)

  pinMode(buttonPin, INPUT_PULLUP);
  debouncer.attach(buttonPin);
  debouncer.interval(50); // debounce 50ms

  lcd.init();
  lcd.backlight();
  updateLCDLine(0, "Menghubungkan...");
  updateLCDLine(1, "");

  WiFi.begin(ssid, password);
  Serial.print("Menghubungkan ke WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nTerhubung ke WiFi");
  Serial.println(WiFi.localIP());

  showLCD();

  server.on("/unlock", handleUnlock);
  server.begin();
}

// ================= Loop =================
void loop() {
  server.handleClient();

  // Ganti tampilan LCD tiap 3 detik
  if (millis() - lastSwitchTime >= 3000) {
    showIP = !showIP;
    showLCD();
    lastSwitchTime = millis();
  }

  // Update tombol
  debouncer.update();
  if (debouncer.fell()) {
    Serial.println("Tombol ditekan, membuka pintu");
    bukaPintu("BUTTON");
  }

  // Tutup pintu otomatis
  if (doorOpen && millis() - doorOpenTime >= doorOpenDuration) {
    tutupPintu();
  }
}
