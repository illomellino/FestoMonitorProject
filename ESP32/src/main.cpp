/*
  ESP32 + ADS1115 - Lettura 2x Vdc (Pressione + Portata)
  Input segnale: 0.6 Vdc a 3.3 Vdc
  Invia dati via seriale USB a 115200 baud
  Formato: timestamp_ms,pressione_bar,portata_Nl,voltage_p_V,voltage_f_V
*/

#include <Wire.h>
#include <Adafruit_ADS1X15.h>

Adafruit_ADS1115 ads; // Crea l'oggetto per la scheda ADS1115

// Range dei sensori (Modifica i valori MAX in base ai tuoi datasheet)
const float PRESSURE_MIN = 0.0;   // bar a 0.6 V
const float PRESSURE_MAX = 10.0;  // bar a 3.3 V
const float FLOW_MIN     = 0.0;   // Nl a 0.6 V
const float FLOW_MAX     = 1000.0;// Nl a 3.3 V

void setup() {
  Serial.begin(115200);
  
  // Inizializza l'I2C sui pin standard dell'ESP32 (SDA=21, SCL=22)
  Wire.begin(21, 22);

  // Imposta il guadagno: GAIN_ONE offre un range di +/- 4.096V
  // 1 bit corrisponde a 0.125mV (0.000125V). Perfetto per un segnale fino a 3.3V.
  ads.setGain(GAIN_ONE);

  if (!ads.begin(0x48)) { // Indirizzo I2C standard dell'ADS1115
    Serial.println("Errore: Impossibile trovare la scheda ADS1115!");
    while (1);
  }
  
  delay(1000);
  Serial.println("ESP32 Air Meter ready (with ADS1115)");
}

float mapVoltage(float voltage, float minVal, float maxVal) {
  // Fault se il segnale scende sotto lo zero dello strumento (es. 0.5V per dare margine sul filo interrotto)
  if (voltage < 0.50) return -999.0;          
  // Overrange se supera leggermente i 3.3V massimi dello strumento
  if (voltage > 3.40) return -998.0;         
  
  // Mappatura lineare sul range specifico 0.6V - 3.3V
  // Formula: Valore = Min + ((V - Vmin) / (Vmax - Vmin)) * (Max - Min)
  return minVal + ((voltage - 0.60) / (3.30 - 0.60)) * (maxVal - minVal);
}

void loop() {
  // Legge i canali analogici dall'ADS1115
  int16_t adc0 = ads.readADC_SingleEnded(0); // Canale A0 per Pressione
  int16_t adc1 = ads.readADC_SingleEnded(1); // Canale A1 per Portata

  // Converte i passi dell'ADC in Volt reali 
  float voltP = adc0 * 0.000125;
  float voltF = adc1 * 0.000125;

  // Calcola i valori fisici convertiti
  float pressure = mapVoltage(voltP, PRESSURE_MIN, PRESSURE_MAX);
  float flow     = mapVoltage(voltF, FLOW_MIN, FLOW_MAX);

  // Trasmette i dati formattati in CSV tramite seriale
  Serial.printf("%lu,%.3f,%.2f,%.2f,%.2f\n",
                millis(), pressure, flow, voltP, voltF);

  delay(200);   // Campionamento a 5 Hz
}
