#include <WiFi.h>
#include <WebServer.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// === Konfigurasi WiFi ===
const char* ssid = "FRR";
const char* password = "Durengede7";

// === Web Server ===
WebServer server(80);
const int relayPin = 5;     // Pin relay
const int buttonPin = 4;    // Pin push button (gunakan GPIO4 misalnya)

// === LCD I2C ===
LiquidCrystal_I2C lcd(0x27, 16, 2);

// === Variabel status pintu ===
String doorStatus = "PINTU TERTUTUP";

// === Variabel untuk ganti tampilan LCD ===
unsigned long lastSwitchTime = 0;
bool showIP = true;

// === Variabel kontrol pintu non-blocking ===
bool doorOpen = false;
unsigned long doorOpenTime = 0;
const unsigned long doorOpenDuration = 5000; // 5 detik

// === Variabel tombol dengan debounce ===
bool buttonState = HIGH;        // state tombol stabil terakhir
bool lastStableState = HIGH;    // untuk deteksi perubahan
unsigned long lastDebounceTime = 0;
const unsigned long debounceDelay = 50; // 50 ms untuk filter bouncing

void showLCD() {
  lcd.clear();
  if (showIP) {
    lcd.setCursor(0, 0);
    lcd.print("IP Address:");
    lcd.setCursor(0, 1);
    lcd.print(WiFi.localIP().toString());
  } else {
    lcd.setCursor(0, 0);
    lcd.print("Status Pintu:");
    lcd.setCursor(0, 1);
    lcd.print(doorStatus);
  }
}

// Fungsi buka pintu (hanya jalan kalau pintu tertutup)
void bukaPintu(String source = "UNKNOWN") {
  if (doorOpen) {
    Serial.println("Request diabaikan, pintu masih terbuka (" + source + ")");
    return;
  }

  digitalWrite(relayPin, LOW); // Relay aktif (LOW)
  doorStatus = "PINTU TERBUKA";
  Serial.println("Buka Pintu via " + source);

  doorOpen = true;
  doorOpenTime = millis();
  showLCD();
}

void handleUnlock() {
  bukaPintu("WEB/QR");
  server.send(200, "text/plain", "Pintu Terbuka");
}

void setup() {
  Serial.begin(115200);

  pinMode(relayPin, OUTPUT);
  digitalWrite(relayPin, HIGH); // relay OFF (pintu tertutup)

  pinMode(buttonPin, INPUT_PULLUP); // tombol aktif LOW

  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("Menghubungkan...");

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

void loop() {
  server.handleClient();

  // Ganti tampilan LCD tiap 3 detik
  if (millis() - lastSwitchTime >= 3000) {
    showIP = !showIP;
    showLCD();
    lastSwitchTime = millis();
  }

  // === Tombol dengan debounce ===
  int reading = digitalRead(buttonPin);

  if (reading != buttonState) {
    lastDebounceTime = millis();  // reset timer saat ada perubahan
    buttonState = reading;        // simpan sementara (belum stabil)
  }

  if ((millis() - lastDebounceTime) > debounceDelay) {
    // jika state stabil berubah
    if (lastStableState != buttonState) {
      lastStableState = buttonState;

      // deteksi tombol ditekan (HIGH -> LOW)
      if (buttonState == LOW) {
        Serial.println("Tombol ditekan, membuka pintu");
        bukaPintu("BUTTON");
      }
    }
  }

  // === Tutup pintu otomatis setelah 5 detik ===
  if (doorOpen && millis() - doorOpenTime >= doorOpenDuration) {
    digitalWrite(relayPin, HIGH); // relay OFF
    doorStatus = "PINTU TERTUTUP";
    Serial.println(doorStatus);
    doorOpen = false;
    showLCD();
  }
}
