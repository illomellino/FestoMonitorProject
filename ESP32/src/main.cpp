/*
  ESP32 + ADS1115 - Lettura 2x Vdc (Pressione + Portata)
  ------------------------------------------------------
  Input segnale: 0.6 Vdc … 3.3 Vdc
  Invia dati via seriale USB a 115200 baud

  Formato CSV:
    timestamp_ms,pressione_bar,portata_Nl_min,voltage_p_V,voltage_f_V

  Codici di fault:
    -999.0  → segnale sotto 0.50 V  (cavo interrotto / sensore spento)
    -998.0  → segnale sopra 3.40 V  (overrange)
*/

#include <Wire.h>
#include <Adafruit_ADS1X15.h>

Adafruit_ADS1115 ads;

// ------------------------------------------------------------------
// Range fisici dei sensori (modifica in base ai datasheet)
const float PRESSURE_MIN = 0.0;     // bar   @ 0.6 V
const float PRESSURE_MAX = 16.0;    // bar   @ 3.3 V
const float FLOW_MIN     = 0.0;     // Nl/min @ 0.6 V
const float FLOW_MAX     = 3000.0;  // Nl/min @ 3.3 V

// Soglie di validità del segnale elettrico
const float V_MIN_VALID  = 0.50;    // sotto questa soglia → fault cavo
const float V_MAX_VALID  = 3.40;    // sopra questa soglia → overrange
const float V_SCALE_MIN_F  = 0.595;    // zero strumento flusso
const float V_SCALE_MAX_F  = 2.97;    // fondo scala strumento flusso
const float V_SCALE_MIN_P  = 0.579;    // zero strumento pressione
const float V_SCALE_MAX_P  = 2.905;    // fondo scala strumento pressione

// Fattore di conversione ADS1115 @ GAIN_ONE (±4.096 V)
// 1 LSB = 0.125 mV = 0.000125 V
const float ADS_LSB = 0.000125f;

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 2000);   // attende USB (utile su alcuni board)

  // I2C standard ESP32: SDA=21, SCL=22
  Wire.begin(21, 22);

  // GAIN_ONE → range ±4.096 V (perfetto per 0-3.3 V)
  ads.setGain(GAIN_ONE);

  if (!ads.begin(0x48)) {               // indirizzo standard ADS1115
    // Stampa l'errore periodicamente così viene sempre intercettato
    // anche se la GUI si connette dopo l'avvio (o se il reset DTR fallisce)
    while (true) {
      Serial.println("Errore: ADS1115 non trovata!");
      delay(2000);
    }
  }

  delay(500);
  Serial.println("ESP32 Air Meter ready (ADS1115 @ GAIN_ONE)");
}

/**
 * Mappa tensione → valore fisico con gestione fault.
 * Ritorna -999.0 (sottorange) o -998.0 (overrange) se fuori limiti.
 */
float mapVoltage(float voltage,float v_scale_min, float v_scale_max, float minVal, float maxVal) {
  if (voltage < V_MIN_VALID) return -999.0f;   // cavo / sensore scollegato
  if (voltage > V_MAX_VALID) return -998.0f;   // overrange

  // Mappatura lineare 0.6 V … 3.3 V → minVal … maxVal
  float ratio = (voltage - v_scale_min) / (v_scale_max - v_scale_min);
  // Clamp per sicurezza (eventuali piccole variazioni di calibrazione)
  if (ratio < 0.0f) ratio = 0.0f;
  if (ratio > 1.0f) ratio = 1.0f;

  return minVal + ratio * (maxVal - minVal);
}

void loop() {
  // Lettura ADC (media di 4 campioni per ridurre rumore)
  int32_t sum0 = 0, sum1 = 0;
  for (int i = 0; i < 4; i++) {
    sum0 += ads.readADC_SingleEnded(0);   // A0 = Pressione
    sum1 += ads.readADC_SingleEnded(1);   // A1 = Portata
  }
  float voltP = (sum0 / 4.0f) * ADS_LSB;
  float voltF = (sum1 / 4.0f) * ADS_LSB;

  // Conversione in grandezze fisiche
  float pressure = mapVoltage(voltP,V_SCALE_MIN_P, V_SCALE_MAX_P, PRESSURE_MIN, PRESSURE_MAX);
  float flow     = mapVoltage(voltF,V_SCALE_MIN_F, V_SCALE_MAX_F, FLOW_MIN, FLOW_MAX);

  // Trasmissione CSV
  // %.3f pressione, %.2f portata, %.3f tensioni (più precise)
  Serial.printf("%lu,%.3f,%.2f,%.3f,%.3f\n",
                millis(),
                pressure,
                flow,
                voltP,
                voltF);

  delay(100);   // 10 Hz
}
